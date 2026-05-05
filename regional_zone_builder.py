"""
regional_zone_builder.py -- regional 권역 기반 출발지 후보 생성·검증·캐싱

진입점: generate_zone_candidates(conn, region) → list[dict]
"""

import logging
import time
from math import radians, sin, cos, sqrt, atan2

import psycopg2.extras

import anchor_definitions

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

ZONE_RADIUS_STEPS  = [10.0, 15.0, 25.0]  # km (단계적 확대)
ZONE_MERGE_RADIUS  = 4.0                  # km (이 이내 권역은 병합)
ZONE_MAX_SHOW      = 10                   # 더보기 포함 최대 노출 수
ZONE_DEFAULT_SHOW  = 5                    # 기본 노출 수
ZONE_TEST_LIMIT    = 8                    # build_course 테스트 상한
MAX_ANCHOR_CANDS   = 40                   # 앵커 후보 상한 (view_count 상위)

# urban 출발 권역 상수
URBAN_ZONE_RADIUS_KM    = 3.0   # 클러스터 반경
URBAN_ZONE_MERGE_KM     = 2.0   # 병합 임계 거리
URBAN_MAX_ANCHOR_CANDS  = 30    # 앵커 후보 상한
URBAN_MIN_SPOTS_IN_ZONE = 2     # 권역 내 최소 spot/culture 수
URBAN_VIEW_PERCENTILE   = 0.60  # 이 이상 = 상위 40%

# 품질 기준 -- Primary
QUALITY_SPOT_MIN   = 2   # spot + culture 합계
QUALITY_MEAL_MIN   = 1
QUALITY_CAFE_MIN   = 1
# 품질 기준 -- Supplementary
QUALITY_SUP_SPOT   = 1
QUALITY_SUP_MEAL   = 1

# regional 코스 생성 파라미터 (course_builder와 동일하게 유지)
REGIONAL_MAX_RADIUS_KM    = 20.0
REGIONAL_FALLBACK_RADIUS  = 30.0
REGIONAL_MAX_TRAVEL_MIN   = 50
REGIONAL_MAX_TOTAL_TRAVEL = 180

# 캐시
_zone_cache: dict = {}
CACHE_TTL = 3600  # 1시간


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    la1, lo1, la2, lo2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = la2 - la1
    dlon = lo2 - lo1
    a = sin(dlat / 2) ** 2 + cos(la1) * cos(la2) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _fetch_all_region_places(conn, region: str) -> list:
    """지역 내 is_active=True, 좌표 있는 전체 장소 반환."""
    sql = """
        SELECT place_id, name, visit_role, latitude, longitude,
               view_count, ai_tags, region_2
        FROM places
        WHERE region_1 = %(region)s
          AND category_id IN (12, 14, 39)
          AND is_active = TRUE
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND visit_role IS NOT NULL
        ORDER BY view_count DESC NULLS LAST
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, {"region": region})
        return [dict(r) for r in cur.fetchall()]


def _places_within(places: list, clat: float, clon: float, radius_km: float) -> list:
    return [
        p for p in places
        if _haversine(clat, clon, p["latitude"], p["longitude"]) <= radius_km
    ]


def _zone_quality(places: list) -> dict:
    spot_cnt  = sum(1 for p in places if p["visit_role"] in ("spot", "culture"))
    meal_cnt  = sum(1 for p in places if p["visit_role"] == "meal")
    cafe_cnt  = sum(1 for p in places if p["visit_role"] == "cafe")
    is_primary = (
        spot_cnt >= QUALITY_SPOT_MIN
        and meal_cnt >= QUALITY_MEAL_MIN
        and cafe_cnt >= QUALITY_CAFE_MIN
    )
    is_supp = (
        not is_primary
        and spot_cnt >= QUALITY_SUP_SPOT
        and meal_cnt >= QUALITY_SUP_MEAL
    )
    return {
        "spot_count": spot_cnt,
        "meal_count": meal_cnt,
        "cafe_count": cafe_cnt,
        "is_primary": is_primary,
        "is_supplementary": is_supp,
    }


def _quality_score(q: dict) -> float:
    return q["spot_count"] * 2.0 + q["meal_count"] * 3.0 + q["cafe_count"] * 2.0


def _find_zone_radius(
    clat: float, clon: float, all_places: list
) -> tuple:
    """최소 통과 반경 탐색. (radius_km, nearby, quality, qtype) 반환. 실패 시 (None,…)."""
    best_supp = None
    for radius in ZONE_RADIUS_STEPS:
        nearby  = _places_within(all_places, clat, clon, radius)
        quality = _zone_quality(nearby)
        if quality["is_primary"]:
            return radius, nearby, quality, "primary"
        if quality["is_supplementary"] and best_supp is None:
            best_supp = (radius, nearby, quality, "supplementary")
    return best_supp if best_supp else (None, [], {}, None)


def _merge_zones(zones: list) -> list:
    """ZONE_MERGE_RADIUS 이내 권역 병합. 품질 점수 높은 쪽 유지."""
    zones = sorted(zones, key=lambda z: (
        0 if z["quality_type"] == "primary" else 1,
        -z["quality_score"],
    ))
    merged = []
    for zone in zones:
        too_close = any(
            _haversine(zone["center_lat"], zone["center_lon"],
                       m["center_lat"], m["center_lon"]) <= ZONE_MERGE_RADIUS
            for m in merged
        )
        if not too_close:
            merged.append(zone)
    return merged


def _zone_name(zone_places: list, region: str) -> str:
    spots = sorted(
        [p for p in zone_places if p["visit_role"] in ("spot", "culture")],
        key=lambda p: (p.get("view_count") or 0),
        reverse=True,
    )
    if spots:
        return f"{spots[0]['name']} 주변"
    if zone_places:
        return f"{zone_places[0]['name']} 주변"
    return f"{region} 주변"


def _is_valid_course(result: dict) -> bool:
    """build_course 결과 통과 기준 검사."""
    if "error" in result:
        return False
    places = result.get("places", [])
    if len(places) < 3:
        return False
    if not any(p.get("visit_role") == "meal" for p in places):
        return False
    if result.get("total_travel_min", 9999) > REGIONAL_MAX_TOTAL_TRAVEL:
        return False
    if not places[-1].get("scheduled_end"):
        return False
    return True


def _test_zone_steps(conn, region: str, center_lat: float, center_lon: float) -> float | None:
    """
    10 → 15 → 25km 단계 확장으로 build_course를 실행해
    최초 성공한 radius_km를 반환. 전 단계 실패 시 None.

    SQL 후보 필터와 per-leg scoring 모두 해당 step radius를 사용.
    """
    import course_builder  # 순환 임포트 방지

    for step in ZONE_RADIUS_STEPS:
        result = course_builder.build_course(conn, {
            "region":             region,
            "companion":          "",
            "themes":             [],
            "template":           "standard",
            "start_time":         "14:00",
            "region_travel_type": "regional",
            "zone_center":        (center_lat, center_lon),
            "zone_radius_km":     step,
        })
        if _is_valid_course(result):
            return step

    return None


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def generate_zone_candidates(conn, region: str) -> list:
    """
    regional 권역 후보 생성·검증.

    Returns
    -------
    list of dict:
        zone_id, center_lat, center_lon, radius_km, name,
        quality, quality_type, quality_score,
        anchor_place_id, anchor_place_name,
        representative_places,
        build_tested, build_passed,
        is_primary
    """
    cache_key = f"{region}:regional"
    now = time.time()
    cached = _zone_cache.get(cache_key)
    if cached and now - cached["ts"] < CACHE_TTL:
        logger.info("zone cache hit -- region=%s", region)
        return cached["zones"]

    all_places = _fetch_all_region_places(conn, region)
    if not all_places:
        logger.warning("zone 생성 불가 -- region=%s 장소 없음", region)
        return []

    anchors = [p for p in all_places if p["visit_role"] in ("spot", "culture")][:MAX_ANCHOR_CANDS]

    raw_zones = []
    for anchor in anchors:
        radius, nearby, quality, qtype = _find_zone_radius(
            anchor["latitude"], anchor["longitude"], all_places
        )
        if radius is None:
            continue
        raw_zones.append({
            "zone_id":             str(anchor["place_id"]),
            "center_lat":          anchor["latitude"],
            "center_lon":          anchor["longitude"],
            "radius_km":           radius,        # build 검증 후 verified_radius_km으로 갱신
            "quality_radius_km":   radius,        # 품질 통과 반경 (불변)
            "verified_radius_km":  None,          # build 검증 후 채워짐
            "anchor_place_id":     anchor["place_id"],
            "anchor_place_name":   anchor["name"],
            "quality":             quality,
            "quality_type":        qtype,
            "quality_score":       _quality_score(quality),
            "name":                _zone_name(nearby, region),
            "representative_places": [
                {"place_id": p["place_id"], "name": p["name"], "visit_role": p["visit_role"]}
                for p in sorted(nearby, key=lambda x: (x.get("view_count") or 0), reverse=True)[:5]
            ],
            "build_tested":  False,
            "build_passed":  False,
            "is_primary":    qtype == "primary",
        })

    merged = _merge_zones(raw_zones)

    primary = [z for z in merged if z["quality_type"] == "primary"]
    supp    = [z for z in merged if z["quality_type"] == "supplementary"]

    tested_primary = []
    for zone in primary[:ZONE_TEST_LIMIT]:
        verified_r = _test_zone_steps(conn, region, zone["center_lat"], zone["center_lon"])
        zone["build_tested"]      = True
        zone["build_passed"]      = verified_r is not None
        zone["verified_radius_km"] = verified_r
        if verified_r is not None:
            zone["radius_km"] = verified_r   # 실제 코스 생성 시 사용할 반경으로 갱신
        logger.info(
            "zone test -- %s quality_r=%.0fkm verified_r=%s passed=%s",
            zone["name"], zone.get("quality_radius_km", 0),
            f"{verified_r:.0f}km" if verified_r else "None",
            verified_r is not None,
        )
        if verified_r is not None:
            tested_primary.append(zone)

    final = tested_primary[:ZONE_MAX_SHOW] + supp[:3]

    _zone_cache[cache_key] = {"zones": final, "ts": now}
    logger.info(
        "zone candidates done -- region=%s total=%d (primary=%d supp=%d)",
        region, len(final), len(tested_primary), len(supp),
    )
    return final


# ---------------------------------------------------------------------------
# anchor 기반 출발 기준점 검증 (urban + regional 공통)
# ---------------------------------------------------------------------------

# 코스 생성 가능 최소 기준 (10km 내)
ANCHOR_TOURIST_MIN = 2   # spot + culture 합계
ANCHOR_MEAL_MIN    = 1   # 식당
# 이하 기준이면 노출 제외, 15/25km 데이터는 진단 전용


def _validate_anchor(conn, region: str, lat: float, lon: float) -> dict:
    """
    anchor 좌표 기준 10/15/25km 반경 내 DB 후보 수 단일 쿼리로 조회.

    visit_role = spot/culture/meal/cafe 만 집계 (출발지 후보 선별 전용).
    course_builder의 slot 필터와 무관하게 전체 활성 장소 수를 반환.
    """
    sql = """
        SELECT
            COUNT(*) FILTER (WHERE visit_role IN ('spot','culture') AND dist <= 10) AS tourist_10km,
            COUNT(*) FILTER (WHERE visit_role = 'meal'              AND dist <= 10) AS meal_10km,
            COUNT(*) FILTER (WHERE visit_role = 'cafe'              AND dist <= 10) AS cafe_10km,
            COUNT(*) FILTER (WHERE                                      dist <= 10) AS total_10km,
            COUNT(*) FILTER (WHERE visit_role IN ('spot','culture') AND dist <= 15) AS tourist_15km,
            COUNT(*) FILTER (WHERE visit_role = 'meal'              AND dist <= 15) AS meal_15km,
            COUNT(*) FILTER (WHERE                                      dist <= 15) AS total_15km,
            COUNT(*) FILTER (WHERE                                      dist <= 25) AS total_25km
        FROM (
            SELECT visit_role,
                   (6371.0 * 2 * ASIN(SQRT(
                       POWER(SIN((RADIANS(latitude)  - RADIANS(%(lat)s)) / 2), 2) +
                       COS(RADIANS(%(lat)s)) * COS(RADIANS(latitude)) *
                       POWER(SIN((RADIANS(longitude) - RADIANS(%(lon)s)) / 2), 2)
                   ))) AS dist
            FROM places
            WHERE region_1  = %(region)s
              AND is_active = TRUE
              AND category_id IN (12, 14, 39)
              AND latitude  IS NOT NULL
              AND longitude IS NOT NULL
              AND visit_role IN ('spot', 'culture', 'meal', 'cafe')
        ) t
        WHERE dist <= 25
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, {"region": region, "lat": lat, "lon": lon})
        row = dict(cur.fetchone())
    return {k: int(v or 0) for k, v in row.items()}


def _anchor_score(counts: dict, anchor: dict) -> float:
    """
    anchor 종합 점수.

    가중치:
      관광지 * 3 + 식당 * 2 + 카페 * 1   (후보 밀집도)
      + 균형 보너스 10점 (tourist≥2, meal≥1, cafe≥1 모두 충족)
      + 대표성 보너스: (10 - priority) * 1.5   (priority 낮을수록 대표적)
    """
    t = counts["tourist_10km"]
    m = counts["meal_10km"]
    c = counts["cafe_10km"]
    density  = t * 3.0 + m * 2.0 + c * 1.0
    balance  = 10.0 if (t >= ANCHOR_TOURIST_MIN and m >= ANCHOR_MEAL_MIN and c >= 1) else 0.0
    rep      = max(0.0, (10 - anchor.get("priority", 9))) * 1.5
    return round(density + balance + rep, 2)


def _anchor_sort_reason(counts: dict) -> str:
    parts = []
    if counts["tourist_10km"]:
        parts.append(f"관광지 {counts['tourist_10km']}개")
    if counts["meal_10km"]:
        parts.append(f"식당 {counts['meal_10km']}개")
    if counts["cafe_10km"]:
        parts.append(f"카페 {counts['cafe_10km']}개")
    return ", ".join(parts) if parts else "코스 생성 가능"


def generate_anchor_departures(conn, region: str, max_anchors: int = 8) -> list:
    """
    지역별 대표 anchor 기반 출발 기준점 후보 생성.

    흐름
    ----
    1. anchor_definitions.REGION_ANCHORS 에서 지역 anchor 목록 조회.
    2. 사전 정의 없는 지역 → generate_urban_departure_zones 로 fallback.
    3. 각 anchor: _validate_anchor 로 10/15/25km DB 후보 수 검증.
    4. tourist_10km < ANCHOR_TOURIST_MIN or meal_10km < ANCHOR_MEAL_MIN → 제외.
    5. anchor_score 내림차순 정렬 → max_anchors개 반환.

    Returns
    -------
    list of dict with keys:
        anchor_id, anchor_name, display_name,
        center_lat, center_lon,
        anchor_score,
        candidate_count_10km, candidate_count_15km, candidate_count_25km,
        tourist_count, meal_count, cafe_count,
        sort_reason, viable
    """
    cache_key = f"{region}:anchor_departures"
    now = time.time()
    cached = _zone_cache.get(cache_key)
    if cached and now - cached["ts"] < CACHE_TTL:
        logger.info("anchor_departures cache hit -- region=%s", region)
        return cached["zones"]

    raw_anchors = anchor_definitions.REGION_ANCHORS.get(region, [])

    # 사전 정의 없는 지역: DB 클러스터링 fallback
    if not raw_anchors:
        logger.info(
            "anchor_departures: 사전 정의 없음 → DB 클러스터링 fallback (region=%s)", region
        )
        result = generate_urban_departure_zones(conn, region, max_zones=max_anchors)
        _zone_cache[cache_key] = {"zones": result, "ts": now}
        return result

    viable   = []
    excluded = []

    for anchor in raw_anchors:
        counts = _validate_anchor(
            conn, region, anchor["latitude"], anchor["longitude"]
        )

        tourist = counts["tourist_10km"]
        meal    = counts["meal_10km"]

        # 코스 생성 불가 판정
        if tourist < ANCHOR_TOURIST_MIN or meal < ANCHOR_MEAL_MIN:
            excl_reason = (
                f"10km 내 관광지 {tourist}개 (최소 {ANCHOR_TOURIST_MIN}개 필요)"
                if tourist < ANCHOR_TOURIST_MIN
                else f"10km 내 식당 {meal}개 (최소 {ANCHOR_MEAL_MIN}개 필요)"
            )
            excluded.append({**anchor, "excluded_reason": excl_reason, **counts})
            logger.info(
                "anchor excluded -- %s tourist_10km=%d meal_10km=%d [%s]",
                anchor["display_name"], tourist, meal, excl_reason,
            )
            continue

        score = _anchor_score(counts, anchor)
        viable.append({
            "anchor_id":              anchor["anchor_id"],
            "anchor_name":            anchor["anchor_name"],
            "display_name":           anchor["display_name"],
            "center_lat":             anchor["latitude"],
            "center_lon":             anchor["longitude"],
            "anchor_score":           score,
            "candidate_count_10km":   counts["total_10km"],
            "candidate_count_15km":   counts["total_15km"],
            "candidate_count_25km":   counts["total_25km"],
            "tourist_count":          counts["tourist_10km"],
            "meal_count":             counts["meal_10km"],
            "cafe_count":             counts["cafe_10km"],
            "sort_reason":            _anchor_sort_reason(counts),
            "viable":                 True,
            "excluded_reason":        None,
        })

    # anchor_score 내림차순 정렬
    viable.sort(key=lambda x: -x["anchor_score"])
    final = viable[:max_anchors]

    _zone_cache[cache_key] = {"zones": final, "ts": now}
    logger.info(
        "anchor_departures done -- region=%s viable=%d excluded=%d returned=%d",
        region, len(viable), len(excluded), len(final),
    )
    return final


def generate_urban_departure_zones(conn, region: str, max_zones: int = 8) -> list:
    """
    urban 지역용 출발 권역 후보 생성.

    view_count 상위 40% 장소를 앵커로 삼아 3km 반경 클러스터를 구성하고,
    인접 권역을 2km 기준으로 병합한 뒤 품질 점수 상위 max_zones개 반환.

    Returns list of dicts: zone_id, name, center_lat, center_lon,
                           radius_km, spot_count, representative_places
    """
    cache_key = f"{region}:urban"
    now = time.time()
    cached = _zone_cache.get(cache_key)
    if cached and now - cached["ts"] < CACHE_TTL:
        return cached["zones"]

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT place_id, name, visit_role, latitude, longitude, view_count
            FROM places
            WHERE region_1 = %(region)s
              AND category_id IN (12, 14)
              AND visit_role IN ('spot', 'culture')
              AND is_active = TRUE
              AND latitude  IS NOT NULL
              AND longitude IS NOT NULL
              AND view_count > 0
            ORDER BY view_count DESC
            """,
            {"region": region},
        )
        places = [dict(r) for r in cur.fetchall()]

    if not places:
        _zone_cache[cache_key] = {"zones": [], "ts": now}
        return []

    # 상위 40% 필터 (60번째 백분위수 이상만 앵커·클러스터 대상)
    sorted_vc = sorted(p["view_count"] for p in places)
    threshold_idx = int(len(sorted_vc) * URBAN_VIEW_PERCENTILE)
    threshold = sorted_vc[min(threshold_idx, len(sorted_vc) - 1)]
    popular = [p for p in places if p["view_count"] >= threshold]

    anchors = popular[:URBAN_MAX_ANCHOR_CANDS]

    raw_zones = []
    for anchor in anchors:
        nearby = _places_within(popular, anchor["latitude"], anchor["longitude"], URBAN_ZONE_RADIUS_KM)
        if len(nearby) < URBAN_MIN_SPOTS_IN_ZONE:
            continue
        quality_score = sum((p.get("view_count") or 0) for p in nearby)
        top5 = sorted(nearby, key=lambda x: (x.get("view_count") or 0), reverse=True)[:5]
        raw_zones.append({
            "zone_id":    f"urban_{anchor['place_id']}",
            "center_lat": float(anchor["latitude"]),
            "center_lon": float(anchor["longitude"]),
            "radius_km":  URBAN_ZONE_RADIUS_KM,
            "name":       f"{anchor['name']} 주변",
            "spot_count": len(nearby),
            "quality_score": quality_score,
            "representative_places": [
                {"place_id": p["place_id"], "name": p["name"], "visit_role": p["visit_role"]}
                for p in top5
            ],
        })

    if not raw_zones:
        _zone_cache[cache_key] = {"zones": [], "ts": now}
        return []

    # 품질 점수 내림차순 정렬 후 2km 이내 인접 권역 병합
    raw_zones.sort(key=lambda z: -z["quality_score"])
    merged = []
    for zone in raw_zones:
        too_close = any(
            _haversine(zone["center_lat"], zone["center_lon"],
                       m["center_lat"], m["center_lon"]) <= URBAN_ZONE_MERGE_KM
            for m in merged
        )
        if not too_close:
            merged.append(zone)

    final = merged[:max_zones]
    _zone_cache[cache_key] = {"zones": final, "ts": now}
    logger.info(
        "urban departure zones -- region=%s total=%d (raw=%d popular=%d)",
        region, len(final), len(raw_zones), len(popular),
    )
    return final


def get_zone_by_id(conn, region: str, zone_id: str) -> dict | None:
    """
    zone_id로 검증된 권역 조회.

    캐시 히트 시 즉시 반환, 캐시 만료 시 재생성 후 조회.
    zone_id가 존재하지 않으면 None 반환.
    """
    zones = generate_zone_candidates(conn, region)
    return next((z for z in zones if z["zone_id"] == zone_id), None)


def invalidate_cache(region: str | None = None) -> None:
    """캐시 무효화. region=None 이면 전체 삭제."""
    if region is None:
        _zone_cache.clear()
    else:
        for suffix in ("regional", "urban", "anchor_departures"):
            _zone_cache.pop(f"{region}:{suffix}", None)
