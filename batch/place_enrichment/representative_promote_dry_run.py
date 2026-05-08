from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config  # noqa: E402,F401
import db_client  # noqa: E402
from tourism_belt import TOURISM_BELT  # noqa: E402


SOURCE_TYPES = {"TOURAPI", "KAKAO", "NAVER", "MANUAL"}
HARD_RISK_FLAGS = {
    "CATEGORY_RISK",
    "LODGING_RISK",
    "PARKING_LOT_RISK",
    "REGION_UNCLEAR",
}
REVIEW_RISK_FLAGS = {
    "VILLAGE_SCOPE_REVIEW",
    "PORT_SCOPE_REVIEW",
    "INTERNAL_FACILITY_RISK",
    "SUB_FACILITY_RISK",
    "TRAIL_SCOPE_REVIEW",
}
SOFT_GAP_FLAGS = {"IMAGE_MISSING", "OVERVIEW_MISSING"}

KNOWN_WEAK_SEED_REPLACEMENTS = {
    "경포대": "경포호수광장",
    "간월암": "간월도마을",
    "국립경주박물관": "국립경주박물관 신라천년서고",
}


def seed_names() -> set[str]:
    return {seed["name"] for seeds in TOURISM_BELT.values() for seed in seeds}


def fetch_candidates(args: argparse.Namespace) -> list[dict[str, Any]]:
    where = []
    params: dict[str, Any] = {"limit": args.limit}
    if args.approved_only:
        where.append("review_status = 'APPROVED'")
    if args.expected_name:
        where.append("expected_poi_name = %(expected_name)s")
        params["expected_name"] = args.expected_name
    if args.source_type:
        where.append("source_type = %(source_type)s")
        params["source_type"] = args.source_type

    sql = """
        SELECT
            candidate_id,
            expected_poi_name,
            region_1,
            region_2,
            matched_place_id,
            source_type,
            source_place_id,
            source_name,
            category,
            address,
            road_address,
            latitude,
            longitude,
            image_url,
            overview,
            confidence_score,
            representative_status,
            review_status,
            promote_status,
            validation_payload,
            review_payload
        FROM representative_poi_candidates
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY confidence_score DESC NULLS LAST, candidate_id LIMIT %(limit)s"

    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def db_exact_match(conn, expected_name: str, region_1: str) -> dict[str, Any] | None:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT place_id, name, category_id, visit_role, is_active, first_image_url IS NOT NULL AS has_image,
                   overview IS NOT NULL AND length(trim(overview)) > 0 AS has_overview
            FROM places
            WHERE region_1 = %s AND name = %s
            ORDER BY is_active DESC, place_id
            LIMIT 1
            """,
            (region_1, expected_name),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def current_seed_info(expected_name: str) -> dict[str, Any]:
    names = seed_names()
    exact = expected_name in names
    weak = KNOWN_WEAK_SEED_REPLACEMENTS.get(expected_name)
    return {
        "current_seed_exists": exact,
        "current_seed_name": expected_name if exact else weak,
        "current_seed_is_weak_substitute": bool(weak and not exact),
    }


def readiness_for(candidate: dict[str, Any], exact_match: dict[str, Any] | None) -> tuple[str, list[str], str]:
    validation = candidate.get("validation_payload") or {}
    risk_flags = set(validation.get("risk_flags") or [])
    confidence = float(candidate.get("confidence_score") or 0)
    reasons: list[str] = []

    if candidate.get("review_status") != "APPROVED":
        return "NOT_READY", ["candidate is not APPROVED"], "do nothing"
    if candidate.get("promote_status") != "PENDING":
        return "NOT_READY", [f"promote_status is {candidate.get('promote_status')}"], "do nothing"
    if risk_flags & HARD_RISK_FLAGS:
        reasons.extend(sorted(risk_flags & HARD_RISK_FLAGS))
        return "NOT_READY", reasons, "reject or request corrected candidate"
    if risk_flags & REVIEW_RISK_FLAGS:
        reasons.extend(sorted(risk_flags & REVIEW_RISK_FLAGS))
        return "REVIEW_MORE", reasons, "manual representative review before promote"
    if confidence < 85:
        return "REVIEW_MORE", [f"confidence_score below threshold: {confidence}"], "manual review"
    if not candidate.get("latitude") or not candidate.get("longitude"):
        return "NOT_READY", ["missing coordinates"], "collect coordinates"

    if not exact_match and not candidate.get("matched_place_id"):
        reasons.append("new representative POI candidate; no existing places exact match")
        if risk_flags <= SOFT_GAP_FLAGS or not risk_flags:
            return "READY_FOR_MANUAL_PROMOTE", reasons, "manual place staging then seed review"
        return "REVIEW_MORE", sorted(risk_flags), "manual review"

    if risk_flags & SOFT_GAP_FLAGS:
        reasons.extend(sorted(risk_flags & SOFT_GAP_FLAGS))
    return "READY_FOR_MANUAL_PROMOTE", reasons, "manual promote dry-run can proceed"


def recommendation_impact(candidate: dict[str, Any], seed: dict[str, Any], readiness: str) -> dict[str, Any]:
    expected = candidate["expected_poi_name"]
    source_name = candidate["source_name"]
    weak_seed = seed.get("current_seed_is_weak_substitute")
    if readiness != "READY_FOR_MANUAL_PROMOTE":
        summary = "No recommendation impact until candidate is approved for manual promote."
    elif weak_seed:
        summary = (
            f"Keeping current seed '{seed['current_seed_name']}' while preparing '{source_name}' "
            f"would let reviewers compare the weak substitute against the expected landmark '{expected}'."
        )
    elif not seed.get("current_seed_exists"):
        summary = (
            f"'{expected}' has no exact current seed. Manual promote could improve representative coverage "
            "after place staging and seed review."
        )
    else:
        summary = f"'{expected}' already has an exact seed; promote would mainly improve data quality."
    return {
        "representative_quality_improvement_expected": readiness == "READY_FOR_MANUAL_PROMOTE",
        "summary": summary,
    }


def analyze_candidate(conn, candidate: dict[str, Any]) -> dict[str, Any]:
    expected_name = candidate["expected_poi_name"]
    seed = current_seed_info(expected_name)
    exact = db_exact_match(conn, expected_name, candidate["region_1"])
    validation = candidate.get("validation_payload") or {}
    readiness, reasons, expected_action = readiness_for(candidate, exact)
    risks = validation.get("risk_flags") or []
    return {
        "expected_poi_name": expected_name,
        "current_seed_exists": seed["current_seed_exists"],
        "current_seed_name": seed["current_seed_name"],
        "current_seed_is_weak_substitute": seed["current_seed_is_weak_substitute"],
        "approved_candidate": {
            "candidate_id": candidate["candidate_id"],
            "source_type": candidate["source_type"],
            "source_name": candidate["source_name"],
            "source_place_id": candidate["source_place_id"],
            "confidence_score": str(candidate["confidence_score"]),
            "category": candidate["category"],
            "address": candidate["road_address"] or candidate["address"],
            "latitude": candidate["latitude"],
            "longitude": candidate["longitude"],
        },
        "representative_risks": risks,
        "matched_place_id": candidate["matched_place_id"],
        "db_exact_match": exact,
        "expected_action": expected_action,
        "promote_readiness": readiness,
        "readiness_reasons": reasons,
        "recommendation_impact": recommendation_impact(candidate, seed, readiness),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    args.limit = min(max(args.limit, 1), 500)
    args.approved_only = True if args.approved_only is None else args.approved_only
    candidates = fetch_candidates(args)
    conn = db_client.get_connection()
    try:
        analyses = [analyze_candidate(conn, c) for c in candidates]
    finally:
        conn.close()
    readiness_counts: dict[str, int] = {}
    for item in analyses:
        readiness = item["promote_readiness"]
        readiness_counts[readiness] = readiness_counts.get(readiness, 0) + 1
    return {
        "mode": "dry-run",
        "db_write": False,
        "places_changed": False,
        "seed_changed": False,
        "engine_changed": False,
        "approved_only": args.approved_only,
        "candidate_count": len(analyses),
        "readiness_counts": readiness_counts,
        "results": analyses,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run representative POI promote impact analysis.")
    parser.add_argument("--expected-name")
    parser.add_argument("--source-type", choices=sorted(SOURCE_TYPES))
    parser.add_argument("--approved-only", action="store_true", default=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    return parser


def print_human(report: dict[str, Any]) -> None:
    print("[Representative POI Promote Dry-run]")
    print("- db_write: false")
    print("- places_changed: false")
    print("- seed_changed: false")
    print("- engine_changed: false")
    print(f"- candidate_count: {report['candidate_count']}")
    print(f"- readiness_counts: {report['readiness_counts']}")
    for item in report["results"]:
        cand = item["approved_candidate"]
        print()
        print(f"## {item['expected_poi_name']}")
        print(f"- candidate_id: {cand['candidate_id']}")
        print(f"- source: {cand['source_type']} / {cand['source_name']} / score={cand['confidence_score']}")
        print(f"- current_seed: {item['current_seed_name']} (exists={item['current_seed_exists']}, weak={item['current_seed_is_weak_substitute']})")
        print(f"- matched_place_id: {item['matched_place_id']}")
        print(f"- db_exact_match: {bool(item['db_exact_match'])}")
        print(f"- risks: {', '.join(item['representative_risks']) if item['representative_risks'] else 'none'}")
        print(f"- readiness: {item['promote_readiness']}")
        print(f"- expected_action: {item['expected_action']}")
        print(f"- impact: {item['recommendation_impact']['summary']}")


def main() -> int:
    args = build_parser().parse_args()
    report = run(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, default=str, indent=2))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
