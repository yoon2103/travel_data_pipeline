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


DEFAULT_TARGETS = ("경포대", "불국사", "성산일출봉", "전주한옥마을")
SOURCE_TYPES = ("TOURAPI", "KAKAO", "NAVER", "MANUAL")

IMAGE_RISK_FLAGS = {
    "PARKING_LOT_RISK",
    "LODGING_RISK",
    "CATEGORY_RISK",
    "INTERNAL_FACILITY_RISK",
    "SUB_FACILITY_RISK",
    "VILLAGE_SCOPE_REVIEW",
}
OVERVIEW_GAP_FLAG = "OVERVIEW_MISSING"
IMAGE_GAP_FLAG = "IMAGE_MISSING"


def has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def fetch_candidates(args: argparse.Namespace) -> list[dict[str, Any]]:
    where = []
    params: dict[str, Any] = {"limit": args.limit}

    if args.expected_name:
        where.append("expected_poi_name = %(expected_name)s")
        params["expected_name"] = args.expected_name
    elif args.default_targets:
        where.append("expected_poi_name = ANY(%(target_names)s)")
        params["target_names"] = list(DEFAULT_TARGETS)

    if args.approved_only:
        where.append("review_status = 'APPROVED'")
    elif not args.include_review_only:
        where.append("review_status IN ('APPROVED', 'PENDING_REVIEW', 'SKIPPED', 'REJECTED')")

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
            source_payload,
            validation_payload,
            review_payload,
            created_at,
            updated_at
        FROM representative_poi_candidates
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += """
        ORDER BY
            expected_poi_name,
            CASE review_status WHEN 'APPROVED' THEN 0 WHEN 'PENDING_REVIEW' THEN 1 ELSE 2 END,
            confidence_score DESC NULLS LAST,
            candidate_id
        LIMIT %(limit)s
    """

    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_existing_places(expected_names: set[str]) -> dict[str, list[dict[str, Any]]]:
    if not expected_names:
        return {}
    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    place_id,
                    name,
                    region_1,
                    region_2,
                    category_id,
                    visit_role,
                    is_active,
                    first_image_url,
                    overview
                FROM places
                WHERE name = ANY(%s)
                ORDER BY name, is_active DESC, place_id
                """,
                (list(expected_names),),
            )
            rows = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["name"], []).append(row)
    return grouped


def risk_flags(candidate: dict[str, Any]) -> list[str]:
    validation = candidate.get("validation_payload") or {}
    return list(validation.get("risk_flags") or [])


def source_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for source in SOURCE_TYPES:
        source_rows = [c for c in candidates if c["source_type"] == source]
        summary[source] = {
            "candidate_count": len(source_rows),
            "has_image_count": sum(1 for c in source_rows if has_text(c.get("image_url"))),
            "has_overview_count": sum(1 for c in source_rows if has_text(c.get("overview"))),
            "best_candidate": best_candidate_summary(source_rows),
        }
    return summary


def best_candidate_summary(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    best = sorted(
        candidates,
        key=lambda c: (
            c.get("review_status") == "APPROVED",
            float(c.get("confidence_score") or 0),
            has_text(c.get("image_url")),
        ),
        reverse=True,
    )[0]
    return {
        "candidate_id": best["candidate_id"],
        "source_type": best["source_type"],
        "source_name": best["source_name"],
        "review_status": best["review_status"],
        "confidence_score": str(best["confidence_score"]),
        "has_image": has_text(best.get("image_url")),
        "has_overview": has_text(best.get("overview")),
        "risk_flags": risk_flags(best),
    }


def approved_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    approved = [c for c in candidates if c["review_status"] == "APPROVED"]
    if not approved:
        return None
    return sorted(approved, key=lambda c: float(c.get("confidence_score") or 0), reverse=True)[0]


def image_quality_assessment(candidate: dict[str, Any] | None, all_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if not candidate:
        return {
            "representative_image_quality": "UNKNOWN",
            "image_quality_risk": ["NO_APPROVED_CANDIDATE"],
            "landmark_identifiable": None,
            "reason": "No approved representative candidate is available.",
        }

    flags = set(risk_flags(candidate))
    has_image = has_text(candidate.get("image_url"))
    source_images = [c for c in all_candidates if has_text(c.get("image_url"))]

    if not has_image:
        risk = ["APPROVED_CANDIDATE_IMAGE_MISSING"]
        if source_images:
            risk.append("IMAGE_EXISTS_ONLY_IN_UNAPPROVED_SOURCE")
        return {
            "representative_image_quality": "MISSING",
            "image_quality_risk": risk,
            "landmark_identifiable": None,
            "reason": "Approved candidate has no image_url.",
        }

    pollution = sorted(flags & IMAGE_RISK_FLAGS)
    if pollution:
        return {
            "representative_image_quality": "REVIEW_REQUIRED",
            "image_quality_risk": pollution,
            "landmark_identifiable": "REVIEW_REQUIRED",
            "reason": "Image exists, but candidate has representative contamination risk.",
        }

    return {
        "representative_image_quality": "LIKELY_USABLE",
        "image_quality_risk": [],
        "landmark_identifiable": "LIKELY",
        "reason": "Image exists on a candidate without hard image contamination flags.",
    }


def enrichment_readiness(candidate: dict[str, Any] | None, source_info: dict[str, Any]) -> tuple[str, list[str], bool]:
    if not candidate:
        return "NEEDS_MANUAL_CURATION", ["approved representative candidate missing"], True

    has_candidate_image = has_text(candidate.get("image_url"))
    has_candidate_overview = has_text(candidate.get("overview"))
    any_source_image = any(v["has_image_count"] > 0 for v in source_info.values())
    any_source_overview = any(v["has_overview_count"] > 0 for v in source_info.values())

    reasons: list[str] = []
    manual_needed = False

    if not has_candidate_image:
        reasons.append("approved candidate image missing")
        manual_needed = True
    if not has_candidate_overview:
        reasons.append("approved candidate overview missing")
        manual_needed = True

    if not has_candidate_image and not any_source_image:
        reasons.append("no staged source image candidate")
    elif not has_candidate_image and any_source_image:
        reasons.append("image exists in non-approved source; needs review before use")

    if not has_candidate_overview and not any_source_overview:
        reasons.append("no staged source overview candidate")

    if not has_candidate_image and not has_candidate_overview:
        return "NEEDS_MANUAL_CURATION", reasons, manual_needed
    if not has_candidate_image:
        return "READY_WITH_IMAGE_GAP", reasons, manual_needed
    if not has_candidate_overview:
        return "READY_WITH_OVERVIEW_GAP", reasons, manual_needed
    return "READY_FOR_MANUAL_PROMOTE", ["image and overview available on approved candidate"], False


def existing_places_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "exact_match_count": len(rows),
        "has_existing_image": any(has_text(r.get("first_image_url")) for r in rows),
        "has_existing_overview": any(has_text(r.get("overview")) for r in rows),
        "matches": [
            {
                "place_id": r["place_id"],
                "name": r["name"],
                "region_1": r["region_1"],
                "region_2": r["region_2"],
                "is_active": r["is_active"],
                "has_image": has_text(r.get("first_image_url")),
                "has_overview": has_text(r.get("overview")),
            }
            for r in rows[:5]
        ],
    }


def analyze_group(expected_name: str, candidates: list[dict[str, Any]], places: list[dict[str, Any]]) -> dict[str, Any]:
    approved = approved_candidate(candidates)
    sources = source_summary(candidates)
    quality = image_quality_assessment(approved, candidates)
    readiness, reasons, manual_needed = enrichment_readiness(approved, sources)
    return {
        "expected_poi_name": expected_name,
        "representative_candidate": best_candidate_summary([approved] if approved else []),
        "source_image_availability": {
            source: {
                "candidate_count": info["candidate_count"],
                "has_image_count": info["has_image_count"],
            }
            for source, info in sources.items()
        },
        "source_overview_availability": {
            source: {
                "candidate_count": info["candidate_count"],
                "has_overview_count": info["has_overview_count"],
            }
            for source, info in sources.items()
        },
        "existing_places": existing_places_summary(places),
        "representative_image_quality": quality,
        "enrichment_readiness": readiness,
        "readiness_reasons": reasons,
        "manual_curation_required": manual_needed,
        "recommended_next_action": recommended_next_action(readiness, sources, approved),
    }


def recommended_next_action(
    readiness: str,
    sources: dict[str, Any],
    approved: dict[str, Any] | None,
) -> str:
    if not approved:
        return "Review and approve one exact representative candidate before enrichment promote analysis."
    if readiness == "READY_FOR_MANUAL_PROMOTE":
        return "Proceed to manual promote planning; no direct places or seed write."
    if sources["TOURAPI"]["has_image_count"] > 0:
        return "Review TourAPI image candidate first, then add/approve image enrichment candidate if representative."
    if readiness in {"READY_WITH_IMAGE_GAP", "READY_WITH_OVERVIEW_GAP", "NEEDS_MANUAL_CURATION"}:
        return "Use manual curator workflow for image and overview gaps before any representative promote."
    return "Keep in review queue."


def run(args: argparse.Namespace) -> dict[str, Any]:
    args.limit = min(max(args.limit, 1), 500)
    candidates = fetch_candidates(args)
    expected_names = sorted({c["expected_poi_name"] for c in candidates})
    existing = fetch_existing_places(set(expected_names))
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in expected_names}
    for candidate in candidates:
        grouped.setdefault(candidate["expected_poi_name"], []).append(candidate)

    results = [
        analyze_group(name, grouped[name], existing.get(name, []))
        for name in expected_names
    ]
    readiness_counts: dict[str, int] = {}
    for item in results:
        readiness = item["enrichment_readiness"]
        readiness_counts[readiness] = readiness_counts.get(readiness, 0) + 1

    return {
        "mode": "dry-run",
        "db_write": False,
        "places_changed": False,
        "seed_changed": False,
        "engine_changed": False,
        "candidate_row_count": len(candidates),
        "poi_count": len(results),
        "readiness_counts": readiness_counts,
        "results": results,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run representative POI image/overview enrichment audit.")
    parser.add_argument("--expected-name")
    parser.add_argument("--source-type", choices=SOURCE_TYPES)
    parser.add_argument("--approved-only", action="store_true", help="Audit APPROVED rows only.")
    parser.add_argument("--include-review-only", action="store_true", default=True, help="Include review-only staged rows for source availability.")
    parser.add_argument("--default-targets", action="store_true", default=True, help="Default to the four representative POI targets.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=200)
    return parser


def print_human(report: dict[str, Any]) -> None:
    print("[Representative POI Enrichment Audit]")
    print("- mode: dry-run")
    print("- db_write: false")
    print("- places_changed: false")
    print("- seed_changed: false")
    print("- engine_changed: false")
    print(f"- candidate_row_count: {report['candidate_row_count']}")
    print(f"- poi_count: {report['poi_count']}")
    print(f"- readiness_counts: {report['readiness_counts']}")
    for item in report["results"]:
        print()
        print(f"## {item['expected_poi_name']}")
        print(f"- readiness: {item['enrichment_readiness']}")
        print(f"- manual_curation_required: {item['manual_curation_required']}")
        print(f"- representative_candidate: {item['representative_candidate']}")
        print(f"- image_availability: {item['source_image_availability']}")
        print(f"- overview_availability: {item['source_overview_availability']}")
        print(f"- existing_places: {item['existing_places']}")
        print(f"- image_quality: {item['representative_image_quality']}")
        print(f"- next_action: {item['recommended_next_action']}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    report = run(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
