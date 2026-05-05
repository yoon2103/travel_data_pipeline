"""FastAPI HTTP server -- course builder wrapper for the frontend.

Usage:
    uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""

import re
import uuid
import logging
from typing import Optional

import psycopg2.extras
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db_client
import course_builder
import regional_zone_builder
import enrichment_service
from course_builder import _haversine
from region_notices import get_service_level, get_blocked_message
from travel_utils import estimate_travel_minutes

app = FastAPI()
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory course store: course_id -> {region, schedule}
_courses: dict = {}

ADD_CANDIDATE_LIMIT = 10
ADD_CANDIDATE_FETCH_LIMIT = 80
ADD_TOTAL_TRAVEL_RATIO_LIMIT = 0.9
ADD_MAX_ROLE_COUNT = 3


def _course_limits(region: str, result: Optional[dict] = None) -> dict:
    if result and result.get("city_mode"):
        return {"max_total": 100, "max_leg": 25, "max_radius": 4.0}
    profile = course_builder.MOBILITY_PROFILE[course_builder._get_city_type(region)]
    return {
        "max_total": int(profile["max_total"]),
        "max_leg": int(profile["max_travel"]),
        "max_radius": float(profile["max_radius"]),
    }


def _role_counts(places: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for place in places:
        role = place.get("visit_role") or "unknown"
        counts[role] = counts.get(role, 0) + 1
    return counts


def _course_option(themes: Optional[list]) -> str:
    return str((themes or ["default"])[0] or "default")


def _safe_log_course_generation(conn, *, region: str, option: str, result: dict | None = None) -> None:
    result = result or {}
    places = result.get("places") or []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO course_generation_logs
                    (region, option, place_count, total_travel_minutes,
                     selected_radius_km, has_option_notice, missing_slot_reason)
                VALUES
                    (%(region)s, %(option)s, %(place_count)s, %(total_travel_minutes)s,
                     %(selected_radius_km)s, %(has_option_notice)s, %(missing_slot_reason)s)
                """,
                {
                    "region": region,
                    "option": option,
                    "place_count": len(places),
                    "total_travel_minutes": result.get("total_travel_min"),
                    "selected_radius_km": result.get("selected_radius_km"),
                    "has_option_notice": bool(result.get("option_notice")),
                    "missing_slot_reason": result.get("missing_slot_reason"),
                },
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("course_generation_logs 적재 실패: %s", exc)


def _safe_log_course_extend(
    conn,
    *,
    region: str,
    option: str,
    before_place_count: int,
    after_place_count: int | None,
    success: bool,
    fail_reason: str | None = None,
    total_travel_minutes: int | None = None,
) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO course_extend_logs
                    (region, option, before_place_count, after_place_count,
                     success, fail_reason, total_travel_minutes)
                VALUES
                    (%(region)s, %(option)s, %(before_place_count)s, %(after_place_count)s,
                     %(success)s, %(fail_reason)s, %(total_travel_minutes)s)
                """,
                {
                    "region": region,
                    "option": option,
                    "before_place_count": before_place_count,
                    "after_place_count": after_place_count,
                    "success": success,
                    "fail_reason": fail_reason,
                    "total_travel_minutes": total_travel_minutes,
                },
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("course_extend_logs 적재 실패: %s", exc)


class GenerateRequest(BaseModel):
    region: str
    departure_time: Optional[str] = None
    start_anchor: Optional[str] = None
    start_lat: Optional[float] = None             # urban 전용: 출발 권역 중심 위도 (직접 좌표)
    start_lon: Optional[float] = None             # urban 전용: 출발 권역 중심 경도 (직접 좌표)
    companion: Optional[str] = ""
    themes: Optional[list] = []
    template: Optional[str] = "standard"
    region_travel_type: Optional[str] = "urban"  # "urban" | "regional"
    zone_id: Optional[str] = None                 # regional 전용: /zones 응답의 zone_id
    walk_max_radius: Optional[float] = None       # urban 전용: 거리 부담 설정 (km)


class ReplaceRequest(BaseModel):
    target_place_id: str
    new_place_id: str


class RecalculatePlace(BaseModel):
    id: str
    place_id: Optional[str] = None
    name: Optional[str] = None
    visit_role: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    duration_min: Optional[int] = None
    first_image_url: Optional[str] = None


class RecalculateRequest(BaseModel):
    place_ids: list[str]
    departure_time: Optional[str] = None
    current_places: Optional[list[RecalculatePlace]] = None


def _candidates_by_role(conn, region: str, role: str, exclude_ids: set, limit: int = 10) -> list:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT place_id, name, visit_role, estimated_duration,
                   latitude, longitude, view_count, rating, review_count,
                   first_image_url
            FROM places
            WHERE region_1 = %(region)s
              AND category_id IN (12, 14, 39)
              AND visit_role = %(role)s
              AND is_active = TRUE
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            ORDER BY view_count DESC NULLS LAST
            LIMIT %(limit)s
            """,
            {"region": region, "role": role, "limit": limit + len(exclude_ids) + 5},
        )
        rows = [dict(r) for r in cur.fetchall()]
    return [r for r in rows if r["place_id"] not in exclude_ids][:limit]


@app.get("/api/regions")
def get_regions():
    """DB에서 is_active 장소가 존재하는 region_1 목록 반환."""
    conn = db_client.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT region_1
                FROM places
                WHERE is_active = TRUE
                  AND region_1 IS NOT NULL
                ORDER BY region_1
                """
            )
            regions = [row[0] for row in cur.fetchall()]
        return {"regions": regions}
    finally:
        conn.close()


@app.get("/api/region/{region}/departures")
def get_region_departures(region: str, limit: int = 8):
    """
    출발 기준점 후보 반환 (anchor 사전 정의 + DB 검증).

    - anchor_definitions.REGION_ANCHORS 에서 지역 anchor 목록 조회.
    - 각 anchor의 10km 반경 관광지/식당/카페 수를 DB로 검증.
    - 코스 생성 불가 anchor 제외 후 anchor_score 내림차순 반환.
    - 사전 정의 없는 지역은 DB 클러스터링 fallback.
    """
    conn = db_client.get_connection()
    try:
        anchors = regional_zone_builder.generate_anchor_departures(conn, region, max_anchors=limit)
        return {
            "region": region,
            "departures": [
                {
                    # UI 필수 필드
                    "zone_id":    a.get("anchor_id") or a.get("zone_id"),
                    "name":       a.get("display_name") or a.get("name"),
                    "center_lat": a.get("center_lat"),
                    "center_lon": a.get("center_lon"),
                    # 진단용 필드 (프론트엔드에서 무시해도 됨)
                    "anchor_score":         a.get("anchor_score"),
                    "candidate_count_10km": a.get("candidate_count_10km"),
                    "candidate_count_15km": a.get("candidate_count_15km"),
                    "candidate_count_25km": a.get("candidate_count_25km"),
                    "tourist_count":        a.get("tourist_count"),
                    "meal_count":           a.get("meal_count"),
                    "cafe_count":           a.get("cafe_count"),
                    "sort_reason":          a.get("sort_reason"),
                }
                for a in anchors
            ],
        }
    finally:
        conn.close()


@app.get("/api/region/{region}/departures/diagnostic")
def get_departures_diagnostic(region: str):
    """
    출발 기준점 후보 진단 리포트 (개발/검증 전용).

    노출 가능/불가능 anchor 전체 목록과 제외 사유 반환.
    프론트엔드에서 사용하지 않음.
    """
    import anchor_definitions as ad

    raw_anchors = ad.REGION_ANCHORS.get(region, [])
    if not raw_anchors:
        return {"region": region, "message": "사전 정의된 anchor 없음", "anchors": []}

    conn = db_client.get_connection()
    try:
        report = []
        for anchor in raw_anchors:
            counts = regional_zone_builder._validate_anchor(
                conn, region, anchor["latitude"], anchor["longitude"]
            )
            tourist = counts["tourist_10km"]
            meal    = counts["meal_10km"]
            viable  = (tourist >= regional_zone_builder.ANCHOR_TOURIST_MIN
                       and meal >= regional_zone_builder.ANCHOR_MEAL_MIN)
            excl_reason = None
            if not viable:
                excl_reason = (
                    f"관광지 {tourist}개 < 최소 {regional_zone_builder.ANCHOR_TOURIST_MIN}"
                    if tourist < regional_zone_builder.ANCHOR_TOURIST_MIN
                    else f"식당 {meal}개 < 최소 {regional_zone_builder.ANCHOR_MEAL_MIN}"
                )
            report.append({
                "anchor_id":              anchor["anchor_id"],
                "display_name":           anchor["display_name"],
                "latitude":               anchor["latitude"],
                "longitude":              anchor["longitude"],
                "priority":               anchor["priority"],
                "viable":                 viable,
                "excluded_reason":        excl_reason,
                "anchor_score":           regional_zone_builder._anchor_score(counts, anchor) if viable else 0,
                "tourist_10km":           counts["tourist_10km"],
                "meal_10km":              counts["meal_10km"],
                "cafe_10km":              counts["cafe_10km"],
                "total_10km":             counts["total_10km"],
                "tourist_15km":           counts["tourist_15km"],
                "total_15km":             counts["total_15km"],
                "total_25km":             counts["total_25km"],
                "sort_reason":            regional_zone_builder._anchor_sort_reason(counts) if viable else "-",
            })
        report.sort(key=lambda x: (-int(x["viable"]), -x["anchor_score"]))
        viable_count   = sum(1 for r in report if r["viable"])
        excluded_count = len(report) - viable_count
        return {
            "region":         region,
            "total_anchors":  len(report),
            "viable_count":   viable_count,
            "excluded_count": excluded_count,
            "anchors":        report,
        }
    finally:
        conn.close()


@app.get("/api/region/{region}/zones")
def get_region_zones(region: str):
    """
    regional 권역 후보 조회.
    품질 검증 + build_course 테스트 통과 권역만 반환.
    """
    conn = db_client.get_connection()
    try:
        zones = regional_zone_builder.generate_zone_candidates(conn, region)
        return {
            "region": region,
            "zones":  [
                {
                    "zone_id":            z["zone_id"],
                    "name":               z["name"],
                    "center_lat":         z["center_lat"],
                    "center_lon":         z["center_lon"],
                    "radius_km":          z["radius_km"],
                    "quality":            z["quality"],
                    "is_primary":         z["is_primary"],
                    "representative_places": z["representative_places"],
                }
                for z in zones
            ],
            "notice": "이 지역은 여행지가 넓게 퍼져 있어 코스가 잘 나오는 출발 권역을 먼저 추천드려요." if zones else None,
            "empty_notice": "코스 생성 가능한 권역이 제한적입니다." if not zones else None,
        }
    finally:
        conn.close()


_FALLBACK_STEPS = [
    {"radius_km": 15, "travel_min": 50, "label": "15km/50분"},
    {"radius_km": 20, "travel_min": 55, "label": "20km/55분"},
    {"radius_km": 25, "travel_min": 60, "label": "25km/60분"},
]


def _is_course_sufficient(result: dict) -> bool:
    """actual이 target-1 이상(최소 3)이면 충분한 코스로 판단.
    light(target=4)에서 3개 이상, standard(target=5)에서 4개 이상, full(target=6)에서 5개 이상이면 통과."""
    actual = len(result.get("places", []))
    target = result.get("target_place_count") or actual
    return actual >= max(3, target - 1)


_FALLBACK_RETRY = 2  # 랜덤 기인 실패 보정: 각 step당 최대 재시도 횟수


def _build_course_with_fallback(conn, base_request: dict) -> dict:
    """10km/40분으로 코스 생성 시도 후, 후보 부족 시 15→20→25km 순으로 완화.
    각 step에서 _weighted_choice 랜덤 기인 실패를 줄이기 위해 _FALLBACK_RETRY 회 재시도."""
    result = course_builder.build_course(conn, base_request)
    if "error" not in result and _is_course_sufficient(result):
        result["radius_fallback"] = False
        return result

    first_radius = float(base_request.get("walk_max_radius") or 10)
    for step in _FALLBACK_STEPS:
        if step["radius_km"] <= first_radius:
            continue
        req = {**base_request, "walk_max_radius": step["radius_km"]}
        best = None
        for _ in range(_FALLBACK_RETRY):
            r = course_builder.build_course(conn, req)
            if "error" not in r and _is_course_sufficient(r):
                best = r
                break
            # 직전 시도보다 장소 수가 많으면 keep
            if best is None or len(r.get("places", [])) > len(best.get("places", [])):
                best = r
        result = best or result
        if "error" not in result and _is_course_sufficient(result):
            label = step["label"]
            result["radius_fallback"]        = True
            result["radius_fallback_label"]  = label
            result["radius_fallback_reason"] = f"후보 부족으로 {label} 적용"
            import logging
            logging.getLogger(__name__).info(
                "radius fallback 적용: %s region=%s", label, base_request.get("region")
            )
            return result

    return {
        "error":              "25km까지 확장해도 코스를 생성할 수 없습니다.",
        "error_code":         "NO_COURSE_ALL_RADIUS",
        "places":             [],
        "radius_fallback":    True,
        "radius_fallback_reason": "10km/15km/20km/25km 모두 후보 부족",
    }


@app.post("/api/course/generate")
def generate_course(body: GenerateRequest):
    if not body.departure_time:
        raise HTTPException(status_code=400, detail="departure_time 필수 (예: '오늘 10:00')")

    conn = db_client.get_connection()
    try:
        option = _course_option(body.themes)
        zone_center    = None
        zone_radius_km = None

        if body.region_travel_type == "regional":
            if not body.zone_id:
                raise HTTPException(
                    status_code=400,
                    detail="regional 코스 생성 시 zone_id 필수 (GET /api/region/{region}/zones 에서 조회)",
                )
            zone = regional_zone_builder.get_zone_by_id(conn, body.region, body.zone_id)
            if zone is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"zone_id={body.zone_id!r} 을 찾을 수 없습니다. 권역 목록을 다시 조회해주세요.",
                )
            zone_center    = (zone["center_lat"], zone["center_lon"])
            zone_radius_km = zone["radius_km"]

        elif body.start_lat is not None and body.start_lon is not None:
            # urban: 출발 권역 좌표를 직접 전달 (generate_urban_departure_zones 결과)
            zone_center = (float(body.start_lat), float(body.start_lon))
            # zone_radius_km은 None → SQL 범위 필터 없음, centroid 안내만 적용

        elif body.start_anchor:
            # fallback: start_anchor 텍스트를 DB에서 찾아 좌표로 변환
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT latitude, longitude
                    FROM places
                    WHERE region_1 = %s
                      AND name ILIKE %s
                      AND is_active = TRUE
                      AND latitude IS NOT NULL
                      AND longitude IS NOT NULL
                    ORDER BY view_count DESC NULLS LAST
                    LIMIT 1
                    """,
                    (body.region, f"%{body.start_anchor}%"),
                )
                row = cur.fetchone()
            if row:
                zone_center = (float(row["latitude"]), float(row["longitude"]))

        request = {
            "region":             body.region,
            "departure_time":     body.departure_time,
            "start_time":         body.departure_time,
            "companion":          body.companion or "",
            "themes":             body.themes or [],
            "template":           body.template or "standard",
            "region_travel_type": body.region_travel_type or "urban",
            "zone_center":        zone_center,
            "zone_radius_km":     zone_radius_km,
            "walk_max_radius":    body.walk_max_radius,
        }

        # BLOCKED 지역: fallback 루프 진입 전에 조기 반환 (BLOCKED 메시지 유실 방지)
        if get_service_level(body.region) == "BLOCKED":
            result = {"error": get_blocked_message(), "places": []}
            _safe_log_course_generation(conn, region=body.region, option=option, result=result)
            return result

        # regional은 zone_radius_km 이 이미 고정돼 있으므로 fallback 없이 직접 호출
        if body.region_travel_type == "regional":
            result = course_builder.build_course(conn, request)
            if "error" in result:
                _safe_log_course_generation(conn, region=body.region, option=option, result=result)
                return result
        else:
            result = _build_course_with_fallback(conn, request)
            if "error" in result:
                _safe_log_course_generation(conn, region=body.region, option=option, result=result)
                return result

        # 노출 전 품질 검증 — meal/cafe 장소에 quality_score/quality_reason 추가
        # 외부 API 실패 시 코스 반환 중단 없음 (graceful pass-through)
        try:
            enrichment_service.validate_course_quality(result)
        except Exception as _qe:
            import logging as _log
            _log.getLogger(__name__).warning("quality validation 실패 (무시): %s", _qe)

        course_id = str(uuid.uuid4())
        result["region_status"] = get_service_level(body.region)
        _courses[course_id] = {
            "region":        body.region,
            "region_status": result["region_status"],
            "option":        option,
            "schedule":      result["places"],
            "limits":        _course_limits(body.region, result),
        }
        result["course_id"] = course_id
        _safe_log_course_generation(conn, region=body.region, option=option, result=result)
        return result
    finally:
        conn.close()


@app.get("/api/course/{course_id}/candidates")
def get_candidates(
    course_id: str,
    place_id: Optional[str] = None,
    role: Optional[str] = "spot",
    insert_after_place_id: Optional[str] = None,
):
    course = _courses.get(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    region   = course["region"]
    schedule = course["schedule"]
    used_ids = {p["place_id"] for p in schedule}

    conn = db_client.get_connection()
    try:
        if not place_id:
            if get_service_level(region) != "FULL":
                raise HTTPException(status_code=400, detail="장소 추가는 정식 지원 지역에서만 가능합니다.")
            if len(schedule) < 5:
                raise HTTPException(status_code=400, detail="장소가 5개 미만인 코스에는 장소를 추가할 수 없습니다.")
            if not insert_after_place_id:
                raise HTTPException(status_code=400, detail="insert_after_place_id는 장소 추가 후보 조회에 필요합니다.")

        candidates = _candidates_by_role(
            conn,
            region,
            role,
            used_ids,
            limit=ADD_CANDIDATE_FETCH_LIMIT if insert_after_place_id else ADD_CANDIDATE_LIMIT,
        )

        if place_id:
            current = next(
                (p for p in schedule if str(p["place_id"]) == str(place_id)),
                None,
            )
            if current and current.get("latitude") and current.get("longitude"):
                clat, clon = float(current["latitude"]), float(current["longitude"])
                for c in candidates:
                    if c.get("latitude") and c.get("longitude"):
                        dist = _haversine(clat, clon, float(c["latitude"]), float(c["longitude"]))
                        c["travel_minutes"] = round(estimate_travel_minutes(dist))

        if insert_after_place_id:
            insert_idx = next(
                (i for i, p in enumerate(schedule) if str(p["place_id"]) == str(insert_after_place_id)),
                None,
            )
            if insert_idx is None:
                raise HTTPException(status_code=404, detail="추가 위치를 찾을 수 없습니다.")

            limits = course.get("limits") or _course_limits(region)
            prev_place = schedule[insert_idx]
            next_place = schedule[insert_idx + 1] if insert_idx + 1 < len(schedule) else None
            if not prev_place.get("latitude") or not prev_place.get("longitude"):
                raise HTTPException(status_code=400, detail="추가 위치의 좌표가 없어 후보를 계산할 수 없습니다.")

            existing_role_counts = _role_counts(schedule)
            filtered = []
            for c in candidates:
                if not c.get("latitude") or not c.get("longitude"):
                    continue
                candidate_role = c.get("visit_role")
                if existing_role_counts.get(candidate_role, 0) >= ADD_MAX_ROLE_COUNT:
                    continue
                if candidate_role and (
                    candidate_role == prev_place.get("visit_role")
                    or (next_place and candidate_role == next_place.get("visit_role"))
                ):
                    continue
                prev_dist = _haversine(
                    float(prev_place["latitude"]),
                    float(prev_place["longitude"]),
                    float(c["latitude"]),
                    float(c["longitude"]),
                )
                prev_travel = round(estimate_travel_minutes(prev_dist))
                if prev_travel > limits["max_leg"] or prev_dist > limits["max_radius"]:
                    continue

                next_travel = None
                next_dist = None
                if next_place and next_place.get("latitude") and next_place.get("longitude"):
                    next_dist = _haversine(
                        float(c["latitude"]),
                        float(c["longitude"]),
                        float(next_place["latitude"]),
                        float(next_place["longitude"]),
                    )
                    next_travel = round(estimate_travel_minutes(next_dist))
                    if next_travel > limits["max_leg"] or next_dist > limits["max_radius"]:
                        continue

                c["travel_minutes"] = prev_travel
                c["distance_km"] = round(prev_dist, 2)
                c["next_travel_minutes"] = next_travel
                c["next_distance_km"] = round(next_dist, 2) if next_dist is not None else None
                filtered.append(c)

            candidates = filtered[:ADD_CANDIDATE_LIMIT]

        return {"candidates": candidates}
    finally:
        conn.close()


@app.post("/api/course/{course_id}/save")
def save_course(course_id: str):
    if course_id not in _courses:
        raise HTTPException(status_code=404, detail="Course not found")
    return {"saved": True, "course_id": course_id}


@app.patch("/api/course/{course_id}/replace")
def replace_place(course_id: str, body: ReplaceRequest):
    course = _courses.get(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    schedule = course["schedule"]
    target_idx = next(
        (i for i, p in enumerate(schedule) if str(p["place_id"]) == str(body.target_place_id)),
        None,
    )
    if target_idx is None:
        raise HTTPException(status_code=404, detail="Target place not found in course")

    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT place_id, name, visit_role, estimated_duration,
                       latitude, longitude, first_image_url
                FROM places WHERE place_id = %s
                """,
                (body.new_place_id,),
            )
            row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="New place not found")

        new_place = dict(row)
        old       = schedule[target_idx]

        replaced = {
            "order":                  old["order"],
            "place_id":               new_place["place_id"],
            "name":                   new_place["name"],
            "visit_role":             new_place["visit_role"],
            "scheduled_start":        old["scheduled_start"],
            "scheduled_end":          old["scheduled_end"],
            "move_minutes_from_prev": old.get("move_minutes_from_prev"),
            "distance_km_from_prev":  old.get("distance_km_from_prev"),
            "travel_to_next_min":     old.get("travel_to_next_min"),
            "distance_to_next_km":    old.get("distance_to_next_km"),
            "latitude":               new_place["latitude"],
            "longitude":              new_place["longitude"],
            "first_image_url":        new_place.get("first_image_url"),
            "fallback_reason":        None,
            "selection_basis":        None,
        }

        updated = list(schedule)
        updated[target_idx] = replaced
        _courses[course_id]["schedule"] = updated

        return {"places": updated}
    finally:
        conn.close()


END_HOUR_LIMIT = 22 * 60  # 22:00 이후 일정 시작 금지


@app.post("/api/course/{course_id}/recalculate")
def recalculate_course(course_id: str, body: RecalculateRequest):
    """
    드래그 재순서 / 장소 추가 후 시간표·이동시간 재계산.
    current_places(프론트 전체 배열)를 기준으로 재계산 — 새 코스 생성 없음.
    추가된 장소(added-* ID)는 place_id로 DB 좌표 조회 후 포함.
    """
    course = _courses.get(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    conn = db_client.get_connection()
    try:
        schedule  = course["schedule"]
        # 서버 저장 데이터 (lat/lon, image 등 완전한 필드 포함)
        srv_map = {str(p["place_id"]): p for p in schedule}

        # current_places가 있으면 프론트 상태 기준으로 목록 구성
        if body.current_places:
            cp_by_id = {cp.id: cp for cp in body.current_places}
        else:
            cp_by_id = {}

        reordered = []
        reordered_client_ids = []
        for pid in body.place_ids:
            if pid in srv_map:
                # 기존 장소: 서버 저장 데이터 사용 (lat/lon 보존)
                reordered.append(dict(srv_map[pid]))
                reordered_client_ids.append(pid)
            elif pid in cp_by_id:
                # 추가된 장소(added-* 등): place_id로 DB에서 좌표/이미지 조회
                cp = cp_by_id[pid]
                db_pid = cp.place_id
                row = None
                if db_pid:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                        cur.execute(
                            """
                            SELECT place_id, name, visit_role, latitude, longitude,
                                   first_image_url, estimated_duration
                            FROM places WHERE place_id = %s
                            """,
                            (db_pid,),
                        )
                        row = cur.fetchone()
                if row:
                    entry = dict(row)
                else:
                    entry = {
                        "place_id":        db_pid or pid,
                        "name":            cp.name or "",
                        "visit_role":      cp.visit_role or "spot",
                        "latitude":        cp.latitude,
                        "longitude":       cp.longitude,
                        "first_image_url": cp.first_image_url,
                        "estimated_duration": None,
                    }
                # 프론트에서 지정한 duration_min 적용
                if cp.duration_min:
                    entry["_override_duration_min"] = cp.duration_min
                reordered.append(entry)
                reordered_client_ids.append(pid)

        if not reordered:
            raise HTTPException(status_code=400, detail="유효한 place_id 없음")

        # 출발시간 파싱
        start_min = 9 * 60
        if body.departure_time:
            m = re.search(r"(\d{1,2}):(\d{2})", body.departure_time)
            if m:
                start_min = int(m.group(1)) * 60 + int(m.group(2))

        updated     = []
        current_min = start_min
        prev_lat    = prev_lon = None

        for i, place in enumerate(reordered):
            # 체류 시간 결정 (우선순위: override → estimated_duration → 기존 스케줄 → 기본값)
            if place.get("_override_duration_min"):
                duration_min = place["_override_duration_min"]
            elif place.get("estimated_duration"):
                duration_min = int(place["estimated_duration"])
            elif place.get("scheduled_start") and place.get("scheduled_end"):
                try:
                    sh, sm = map(int, place["scheduled_start"].split(":"))
                    eh, em = map(int, place["scheduled_end"].split(":"))
                    duration_min = max((eh * 60 + em) - (sh * 60 + sm), 30)
                except Exception:
                    duration_min = 60
            else:
                duration_min = 60

            # 이전 장소 → 현재 장소 이동 시간
            travel_min = 0
            dist_km    = 0.0
            if prev_lat is not None and place.get("latitude") and place.get("longitude"):
                dist_km    = _haversine(float(prev_lat), float(prev_lon),
                                        float(place["latitude"]), float(place["longitude"]))
                travel_min = round(estimate_travel_minutes(dist_km))

            s_min = current_min + travel_min

            # 22:00 시작 초과 시 이후 장소 드롭
            if s_min >= END_HOUR_LIMIT:
                break

            e_min = min(s_min + duration_min, END_HOUR_LIMIT)

            entry = {k: v for k, v in place.items() if k != "_override_duration_min"}
            updated.append({
                **entry,
                "order":                  i + 1,
                "scheduled_start":        f"{s_min // 60:02d}:{s_min % 60:02d}",
                "scheduled_end":          f"{e_min // 60:02d}:{e_min % 60:02d}",
                "move_minutes_from_prev": travel_min if i > 0 else None,
                "distance_km_from_prev":  round(dist_km, 2) if i > 0 else None,
            })

            current_min = e_min
            prev_lat    = place.get("latitude")
            prev_lon    = place.get("longitude")

        total_travel = sum(p.get("move_minutes_from_prev") or 0 for p in updated)
        total_dur    = sum(
            (int(p["scheduled_end"].split(":")[0]) * 60 + int(p["scheduled_end"].split(":")[1])) -
            (int(p["scheduled_start"].split(":")[0]) * 60 + int(p["scheduled_start"].split(":")[1]))
            for p in updated
        )
        added_indexes = [
            i for i, pid in enumerate(reordered_client_ids)
            if pid not in srv_map
        ]
        if added_indexes:
            region = course["region"]
            option = course.get("option") or "default"
            before_count = len(schedule)
            after_count = len(updated)

            def reject_extend(message: str) -> None:
                _safe_log_course_extend(
                    conn,
                    region=region,
                    option=option,
                    before_place_count=before_count,
                    after_place_count=after_count,
                    success=False,
                    fail_reason=message,
                    total_travel_minutes=total_travel,
                )
                raise HTTPException(status_code=400, detail=message)

            if get_service_level(course["region"]) != "FULL":
                reject_extend("장소 추가는 정식 지원 지역에서만 가능합니다.")
            if len(schedule) < 5:
                reject_extend("장소가 5개 미만인 코스에는 장소를 추가할 수 없습니다.")
            if len(added_indexes) > 1:
                reject_extend("장소는 한 번에 1개만 추가할 수 있습니다.")
            if len(updated) != len(reordered):
                reject_extend("추가 후 일정 시간이 초과되어 장소를 추가할 수 없습니다.")

            limits = course.get("limits") or _course_limits(course["region"])
            max_allowed_total = int(limits["max_total"]) * ADD_TOTAL_TRAVEL_RATIO_LIMIT
            if total_travel >= max_allowed_total:
                reject_extend(f"추가 후 이동시간이 기준을 초과합니다. 현재 {total_travel}분 / 기준 {round(max_allowed_total)}분")

            added_idx = added_indexes[0]
            adjacent_checks = []
            if added_idx > 0:
                adjacent_checks.append(updated[added_idx])
            if added_idx + 1 < len(updated):
                adjacent_checks.append(updated[added_idx + 1])
            for place in adjacent_checks:
                leg_time = place.get("move_minutes_from_prev") or 0
                leg_dist = place.get("distance_km_from_prev") or 0
                if leg_time > limits["max_leg"] or leg_dist > limits["max_radius"]:
                    reject_extend("추가 장소와 주변 장소의 이동거리가 너무 멉니다.")

            role_counts = _role_counts(updated)
            if any(count > ADD_MAX_ROLE_COUNT for count in role_counts.values()):
                reject_extend("장소 역할 구성이 한쪽으로 치우쳐 추가할 수 없습니다.")
            added_role = updated[added_idx].get("visit_role")
            prev_role = updated[added_idx - 1].get("visit_role") if added_idx > 0 else None
            next_role = updated[added_idx + 1].get("visit_role") if added_idx + 1 < len(updated) else None
            if added_role and (added_role == prev_role or added_role == next_role):
                reject_extend("같은 유형의 장소가 연속되어 추가할 수 없습니다.")

            _safe_log_course_extend(
                conn,
                region=region,
                option=option,
                before_place_count=before_count,
                after_place_count=after_count,
                success=True,
                fail_reason=None,
                total_travel_minutes=total_travel,
            )

        _courses[course_id]["schedule"] = updated

        return {
            "places":             updated,
            "total_travel_min":   total_travel,
            "total_duration_min": total_dur,
        }
    finally:
        conn.close()
