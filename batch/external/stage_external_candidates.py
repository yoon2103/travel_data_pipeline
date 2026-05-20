from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import db_client  # noqa: E402
from batch.external.common import haversine_km, normalize_name, valid_korea_coord  # noqa: E402


BLOCK_CATEGORY_KEYWORDS = (
    "숙박",
    "모텔",
    "호텔",
    "병원",
    "의원",
    "약국",
    "학교",
    "유치원",
    "어린이집",
    "부동산",
    "주민센터",
    "행정복지",
)

CLOSED_STATUS_VALUES = {"closed", "폐업", "영업종료", "inactive"}


@dataclass
class CandidateRisk:
    clean_external_place_id: int
    source: str
    external_id: str
    external_content_id: str
    name: str
    region: str
    latitude: float | None
    longitude: float | None
    category: str | None
    visit_role: str | None
    address: str | None
    place_url: str | None
    image_available: bool
    coordinate_valid: bool
    duplicate_risk: bool
    duplicate_of_place_id: int | None
    duplicate_match_name: str | None
    match_status: str
    match_confidence: float | None
    business_status: str
    business_safety_status: str
    category_mismatch: bool
    proposed_action: str
    promotion_status: str
    qa_status: str | None
    review_decision: str
    block_reasons: list[str]


def _table_columns(conn, table_name: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            """,
            (table_name,),
        )
        return {row[0] for row in cur.fetchall()}


def _select_expr(columns: set[str], name: str, fallback: str = "NULL") -> str:
    return f"{name}" if name in columns else f"{fallback} AS {name}"


def _load_clean_rows(conn, run_id: str, region: str | None, limit: int, visit_role: str | None = None) -> list[dict[str, Any]]:
    columns = _table_columns(conn, "clean_external_places")
    optional = [
        _select_expr(columns, "rating"),
        _select_expr(columns, "review_count"),
        _select_expr(columns, "image_url"),
        _select_expr(columns, "image_thumb_url"),
        _select_expr(columns, "business_status", "'unknown'"),
        _select_expr(columns, "opening_hours"),
        _select_expr(columns, "last_verified_at"),
        _select_expr(columns, "source_confidence"),
        _select_expr(columns, "duplicate_of_place_id"),
        _select_expr(columns, "match_status", "'unmatched'"),
        _select_expr(columns, "match_confidence"),
    ]
    sql = f"""
        SELECT
            id,
            run_id,
            region,
            source,
            external_id,
            external_content_id,
            name,
            latitude,
            longitude,
            category,
            address,
            phone,
            place_url,
            visit_role,
            duplicate_key,
            normalized_payload,
            {", ".join(optional)}
        FROM clean_external_places
        WHERE run_id = %s
    """
    params: list[Any] = [run_id]
    if region:
        sql += " AND region = %s"
        params.append(region)
    if visit_role:
        sql += " AND visit_role = %s"
        params.append(visit_role)
    sql += " ORDER BY id LIMIT %s"
    params.append(limit)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def _load_existing_places(conn, regions: set[str]) -> list[dict[str, Any]]:
    if not regions:
        return []
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT place_id, name, region_1, latitude, longitude, kakao_place_id, naver_place_id
            FROM places
            WHERE is_active = TRUE
              AND region_1 = ANY(%s)
            """,
            (list(regions),),
        )
        return list(cur.fetchall())


def _business_safety_status(row: dict[str, Any]) -> str:
    status = str(row.get("business_status") or "unknown").strip().lower()
    if status in CLOSED_STATUS_VALUES:
        return "closed"
    if status in {"open", "active", "정상", "영업중"}:
        return "safe"
    return "unknown"


def _category_mismatch(row: dict[str, Any]) -> bool:
    text = f"{row.get('name') or ''} {row.get('category') or ''}"
    return any(keyword in text for keyword in BLOCK_CATEGORY_KEYWORDS)


def _image_available(row: dict[str, Any]) -> bool:
    payload = row.get("normalized_payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    return bool(row.get("image_url") or row.get("image_thumb_url") or payload.get("image_url") or payload.get("first_image_url"))


def _find_duplicate(row: dict[str, Any], existing_places: list[dict[str, Any]]) -> tuple[bool, int | None, str | None, float | None]:
    source = row.get("source")
    external_id = str(row.get("external_id") or "")
    if source == "kakao" and external_id:
        for place in existing_places:
            if place.get("kakao_place_id") == external_id:
                return True, place["place_id"], place["name"], 1.0
    if source == "naver" and external_id:
        for place in existing_places:
            if place.get("naver_place_id") == external_id:
                return True, place["place_id"], place["name"], 1.0

    name_key = normalize_name(str(row.get("name") or ""))
    lat = row.get("latitude")
    lon = row.get("longitude")
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return False, None, None, None

    for place in existing_places:
        if normalize_name(str(place.get("name") or "")) != name_key:
            continue
        try:
            dist = haversine_km(lat_f, lon_f, float(place["latitude"]), float(place["longitude"]))
        except (TypeError, ValueError):
            continue
        if dist <= 0.15:
            confidence = max(0.0, round(1.0 - (dist / 0.15) * 0.2, 3))
            return True, place["place_id"], place["name"], confidence
    return False, None, None, None


def _decision(row: dict[str, Any], duplicate_risk: bool, coord_valid: bool, category_mismatch: bool, business_safety: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if not coord_valid:
        reasons.append("BLOCK_MISSING_COORDINATE")
    if duplicate_risk:
        reasons.append("BLOCK_DUPLICATE_RISK")
    if category_mismatch:
        reasons.append("BLOCK_CATEGORY_RISK")
    if business_safety == "closed":
        reasons.append("BLOCK_CLOSED_BUSINESS")
    if not _image_available(row):
        reasons.append("BLOCK_MISSING_IMAGE")

    hard_blocks = {"BLOCK_MISSING_COORDINATE", "BLOCK_CLOSED_BUSINESS"}
    if any(reason in hard_blocks for reason in reasons):
        return "BLOCK", reasons
    if reasons:
        return "REVIEW_REQUIRED", reasons
    return "APPROVE_CANDIDATE", reasons


def build_candidates(run_id: str, region: str | None, limit: int, visit_role: str | None = None) -> dict[str, Any]:
    conn = db_client.get_connection()
    try:
        rows = _load_clean_rows(conn, run_id, region, limit, visit_role)
        existing = _load_existing_places(conn, {str(row["region"]) for row in rows if row.get("region")})
        candidates: list[CandidateRisk] = []
        for row in rows:
            coord_valid = valid_korea_coord(row.get("latitude"), row.get("longitude"))
            duplicate_risk, duplicate_place_id, duplicate_name, dup_confidence = _find_duplicate(row, existing)
            category_mismatch = _category_mismatch(row)
            business_safety = _business_safety_status(row)
            decision, reasons = _decision(row, duplicate_risk, coord_valid, category_mismatch, business_safety)
            proposed_action = "candidate_update" if duplicate_risk else "candidate_insert"
            candidates.append(
                CandidateRisk(
                    clean_external_place_id=row["id"],
                    source=row["source"],
                    external_id=str(row["external_id"]),
                    external_content_id=row["external_content_id"],
                    name=row["name"],
                    region=row["region"],
                    latitude=float(row["latitude"]) if row.get("latitude") is not None else None,
                    longitude=float(row["longitude"]) if row.get("longitude") is not None else None,
                    category=row.get("category"),
                    visit_role=row.get("visit_role"),
                    address=row.get("address"),
                    place_url=row.get("place_url"),
                    image_available=_image_available(row),
                    coordinate_valid=coord_valid,
                    duplicate_risk=duplicate_risk,
                    duplicate_of_place_id=duplicate_place_id,
                    duplicate_match_name=duplicate_name,
                    match_status="duplicate" if duplicate_risk else "unmatched",
                    match_confidence=dup_confidence,
                    business_status=str(row.get("business_status") or "unknown"),
                    business_safety_status=business_safety,
                    category_mismatch=category_mismatch,
                    proposed_action=proposed_action,
                    promotion_status="pending_review",
                    qa_status=None,
                    review_decision=decision,
                    block_reasons=reasons,
                )
            )
        summary = {
            "run_id": run_id,
            "region": region,
            "visit_role": visit_role,
            "candidate_count": len(candidates),
            "duplicate_suspicious_count": sum(1 for c in candidates if c.duplicate_risk),
            "missing_image_count": sum(1 for c in candidates if not c.image_available),
            "missing_coordinate_count": sum(1 for c in candidates if not c.coordinate_valid),
            "category_mismatch_count": sum(1 for c in candidates if c.category_mismatch),
            "business_closed_or_suspicious_count": sum(1 for c in candidates if c.business_safety_status in {"closed", "suspicious"}),
            "approve_candidate_count": sum(1 for c in candidates if c.review_decision == "APPROVE_CANDIDATE"),
            "review_required_count": sum(1 for c in candidates if c.review_decision == "REVIEW_REQUIRED"),
            "blocked_count": sum(1 for c in candidates if c.review_decision == "BLOCK"),
        }
        return {"summary": summary, "candidates": [asdict(candidate) for candidate in candidates]}
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare external candidates for review gate. Dry-run by default.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--region")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--visit-role", choices=["cafe", "meal", "culture", "spot"], help="Optional slice filter for rehearsal/review reports.")
    parser.add_argument("--write", action="store_true", help="Reserved for a later migration-backed phase. Not enabled by default.")
    args = parser.parse_args()

    result = build_candidates(args.run_id, args.region, args.limit, args.visit_role)
    if args.write:
        result["write"] = False
        result["write_blocked"] = "staging_external_places write is intentionally disabled in this phase"
    else:
        result["write"] = False
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
