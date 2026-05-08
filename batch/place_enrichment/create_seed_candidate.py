from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config  # noqa: E402,F401
import db_client  # noqa: E402


PROMOTE_STRATEGIES = {
    "KEEP_EXISTING_ONLY",
    "COEXIST_WITH_EXISTING",
    "REPLACE_EXISTING",
    "REPRESENTATIVE_ALIAS_ONLY",
}

KNOWN_EXISTING_SEEDS = {
    "경포대": "경포호수광장",
}

HARD_RISK_FLAGS = {
    "REGION_UNCLEAR",
    "CATEGORY_RISK",
    "LODGING_RISK",
    "PARKING_LOT_RISK",
    "INTERNAL_FACILITY_RISK",
    "SUB_FACILITY_RISK",
}


class SeedCandidateError(ValueError):
    pass


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lam / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def fetch_representative_candidate(conn, expected_name: str, region: str | None) -> dict[str, Any] | None:
    where = ["expected_poi_name = %s", "review_status = 'APPROVED'"]
    params: list[Any] = [expected_name]
    if region:
        where.append("region_1 = %s")
        params.append(region)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"""
            SELECT
                candidate_id,
                expected_poi_name,
                region_1,
                region_2,
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
                validation_payload,
                review_payload,
                review_status,
                promote_status
            FROM representative_poi_candidates
            WHERE {' AND '.join(where)}
              AND COALESCE(category, '') NOT IN ('REPRESENTATIVE_IMAGE', 'REPRESENTATIVE_OVERVIEW')
            ORDER BY confidence_score DESC NULLS LAST, candidate_id
            LIMIT 1
            """,
            params,
        )
        row = cur.fetchone()
        return dict(row) if row else None


def fetch_enrichment_status(conn, expected_name: str) -> dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT candidate_id, category, review_status, image_url, overview, source_payload, validation_payload
            FROM representative_poi_candidates
            WHERE expected_poi_name = %s
              AND source_type = 'MANUAL'
              AND category IN ('REPRESENTATIVE_IMAGE', 'REPRESENTATIVE_OVERVIEW')
            ORDER BY candidate_id
            """,
            (expected_name,),
        )
        rows = [dict(row) for row in cur.fetchall()]
    approved_image = next(
        (
            r
            for r in rows
            if r["category"] == "REPRESENTATIVE_IMAGE"
            and r["review_status"] == "APPROVED"
            and has_text(r.get("image_url"))
        ),
        None,
    )
    approved_overview = next(
        (
            r
            for r in rows
            if r["category"] == "REPRESENTATIVE_OVERVIEW"
            and r["review_status"] == "APPROVED"
            and has_text(r.get("overview"))
        ),
        None,
    )
    return {
        "manual_enrichment_candidates": rows,
        "approved_image_candidate": approved_image,
        "approved_overview_candidate": approved_overview,
        "has_approved_image": approved_image is not None,
        "has_approved_overview": approved_overview is not None,
    }


def find_existing_seed_place(conn, seed_name: str | None, region: str | None) -> dict[str, Any] | None:
    if not seed_name:
        return None
    where = ["name = %s"]
    params: list[Any] = [seed_name]
    if region:
        where.append("region_1 = %s")
        params.append(region)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"""
            SELECT place_id, name, region_1, region_2, latitude, longitude, visit_role, category_id, is_active
            FROM places
            WHERE {' AND '.join(where)}
            ORDER BY is_active DESC, place_id
            LIMIT 1
            """,
            params,
        )
        row = cur.fetchone()
        return dict(row) if row else None


def existing_duplicate(conn, payload: dict[str, Any]) -> dict[str, Any] | None:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT seed_candidate_id, expected_poi_name, candidate_place_name, promote_strategy,
                   seed_status, review_status
            FROM seed_candidates
            WHERE region_1 = %s
              AND COALESCE(region_2, '') = COALESCE(%s, '')
              AND expected_poi_name = %s
              AND candidate_place_name = %s
              AND promote_strategy = %s
              AND seed_status NOT IN ('REJECTED', 'ROLLED_BACK')
            ORDER BY seed_candidate_id DESC
            LIMIT 1
            """,
            (
                payload["region_1"],
                payload.get("region_2"),
                payload["expected_poi_name"],
                payload["candidate_place_name"],
                payload["promote_strategy"],
            ),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def build_analysis(
    representative: dict[str, Any],
    enrichment: dict[str, Any],
    *,
    existing_seed_name: str | None,
    existing_seed_place: dict[str, Any] | None,
    strategy: str,
) -> dict[str, Any]:
    risk_flags = set((representative.get("validation_payload") or {}).get("risk_flags") or [])
    risk_flags.discard("IMAGE_MISSING")
    risk_flags.discard("OVERVIEW_MISSING")
    if not enrichment["has_approved_image"]:
        risk_flags.add("IMAGE_MISSING")
    if not enrichment["has_approved_overview"]:
        risk_flags.add("OVERVIEW_MISSING")

    distance_km = None
    duplicate_nearby_risk = "UNKNOWN"
    if (
        existing_seed_place
        and representative.get("latitude") is not None
        and representative.get("longitude") is not None
        and existing_seed_place.get("latitude") is not None
        and existing_seed_place.get("longitude") is not None
    ):
        distance_km = haversine_km(
            float(representative["latitude"]),
            float(representative["longitude"]),
            float(existing_seed_place["latitude"]),
            float(existing_seed_place["longitude"]),
        )
        duplicate_nearby_risk = "HIGH" if distance_km <= 1.0 else "MEDIUM" if distance_km <= 3.0 else "LOW"
    elif existing_seed_name:
        duplicate_nearby_risk = "REVIEW_REQUIRED"

    qa_required = True
    hard_blocks = sorted(risk_flags & HARD_RISK_FLAGS)
    readiness = "READY_FOR_REVIEW"
    if hard_blocks:
        readiness = "NOT_READY"
    elif "IMAGE_MISSING" in risk_flags or "OVERVIEW_MISSING" in risk_flags:
        readiness = "NOT_READY"
    elif strategy == "REPLACE_EXISTING":
        readiness = "NEEDS_REVIEW"

    return {
        "expected_poi_name": representative["expected_poi_name"],
        "existing_seed": {
            "name": existing_seed_name,
            "place": existing_seed_place,
        },
        "overlay_candidate": {
            "representative_candidate_id": representative["candidate_id"],
            "candidate_place_name": representative["expected_poi_name"],
            "source_type": representative["source_type"],
            "source_name": representative["source_name"],
            "confidence_score": str(representative["confidence_score"]),
            "latitude": representative["latitude"],
            "longitude": representative["longitude"],
        },
        "strategy": strategy,
        "risk_flags": sorted(risk_flags),
        "qa_required": qa_required,
        "duplicate_nearby_risk": duplicate_nearby_risk,
        "existing_seed_distance_km": round(distance_km, 3) if distance_km is not None else None,
        "readiness": readiness,
        "readiness_reasons": readiness_reasons(risk_flags, hard_blocks, enrichment, strategy),
        "expected_recommendation_impact": {
            "representative_quality_improvement": representative["expected_poi_name"] != existing_seed_name,
            "place_count_change_expected": "LOW",
            "slot_change_risk": "MEDIUM" if duplicate_nearby_risk in {"HIGH", "MEDIUM"} else "LOW",
            "travel_time_change_risk": "LOW_TO_MEDIUM",
            "regional_bias_risk": "MEDIUM" if strategy in {"COEXIST_WITH_EXISTING", "PRIORITY_OVERRIDE"} else "LOW",
        },
        "enrichment_status": {
            "has_approved_image": enrichment["has_approved_image"],
            "approved_image_candidate_id": (
                enrichment["approved_image_candidate"]["candidate_id"]
                if enrichment["approved_image_candidate"]
                else None
            ),
            "has_approved_overview": enrichment["has_approved_overview"],
            "approved_overview_candidate_id": (
                enrichment["approved_overview_candidate"]["candidate_id"]
                if enrichment["approved_overview_candidate"]
                else None
            ),
        },
    }


def readiness_reasons(
    risk_flags: set[str],
    hard_blocks: list[str],
    enrichment: dict[str, Any],
    strategy: str,
) -> list[str]:
    reasons: list[str] = []
    if hard_blocks:
        reasons.append("hard risk flags block seed candidate readiness")
    if not enrichment["has_approved_image"]:
        reasons.append("approved representative image is missing")
    if not enrichment["has_approved_overview"]:
        reasons.append("approved representative overview is missing")
    if strategy == "REPLACE_EXISTING":
        reasons.append("replace strategy requires explicit QA and rollback review")
    if not reasons:
        reasons.append("candidate can proceed to seed review dry-run")
    return reasons


def build_payload(args: argparse.Namespace, representative: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "region_1": representative["region_1"],
        "region_2": representative.get("region_2"),
        "expected_poi_name": representative["expected_poi_name"],
        "existing_seed_name": analysis["existing_seed"]["name"],
        "representative_candidate_id": representative["candidate_id"],
        "source_type": "REPRESENTATIVE_POI",
        "candidate_place_name": representative["expected_poi_name"],
        "promote_strategy": args.strategy,
        "seed_status": "NEEDS_REVIEW" if analysis["readiness"] == "NOT_READY" else "CANDIDATE",
        "review_status": "PENDING_REVIEW",
        "risk_flags": analysis["risk_flags"],
        "source_payload": {
            "workflow": "seed_candidate_staging",
            "baseline_source": "tourism_belt.py",
            "representative_candidate": analysis["overlay_candidate"],
            "existing_seed": analysis["existing_seed"],
        },
        "validation_payload": {
            "readiness": analysis["readiness"],
            "readiness_reasons": analysis["readiness_reasons"],
            "places_write": False,
            "seed_write": False,
            "engine_integration": False,
        },
        "review_payload": {
            "review_status": "PENDING_REVIEW",
            "review_required": True,
            "review_reason": "seed overlay candidate requires governance review before promote",
        },
        "dry_run_payload": analysis,
        "rollback_payload": {
            "rollback_supported": True,
            "baseline_source": "tourism_belt.py",
            "actual_overlay_applied": False,
        },
    }


def insert_seed_candidate(conn, payload: dict[str, Any]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO seed_candidates (
                region_1, region_2, expected_poi_name, existing_seed_name,
                representative_candidate_id, source_type, candidate_place_name,
                promote_strategy, seed_status, review_status, risk_flags,
                source_payload, validation_payload, review_payload,
                dry_run_payload, rollback_payload
            )
            VALUES (
                %(region_1)s, %(region_2)s, %(expected_poi_name)s, %(existing_seed_name)s,
                %(representative_candidate_id)s, %(source_type)s, %(candidate_place_name)s,
                %(promote_strategy)s, %(seed_status)s, %(review_status)s, %(risk_flags)s,
                %(source_payload)s, %(validation_payload)s, %(review_payload)s,
                %(dry_run_payload)s, %(rollback_payload)s
            )
            ON CONFLICT DO NOTHING
            RETURNING seed_candidate_id
            """,
            {
                **payload,
                "risk_flags": psycopg2.extras.Json(payload["risk_flags"]),
                "source_payload": psycopg2.extras.Json(payload["source_payload"]),
                "validation_payload": psycopg2.extras.Json(payload["validation_payload"]),
                "review_payload": psycopg2.extras.Json(payload["review_payload"]),
                "dry_run_payload": psycopg2.extras.Json(payload["dry_run_payload"]),
                "rollback_payload": psycopg2.extras.Json(payload["rollback_payload"]),
            },
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0


def create_seed_candidate(args: argparse.Namespace) -> dict[str, Any]:
    expected_name = (args.expected_name or "").strip()
    if not expected_name:
        raise SeedCandidateError("expected-name is required")
    strategy = args.strategy
    if strategy not in PROMOTE_STRATEGIES:
        raise SeedCandidateError(f"invalid strategy: {strategy}")

    conn = db_client.get_connection()
    try:
        representative = fetch_representative_candidate(conn, expected_name, args.region)
        if not representative:
            raise SeedCandidateError(f"approved representative candidate does not exist: {expected_name}")
        existing_seed_name = (args.existing_seed_name or "").strip() or KNOWN_EXISTING_SEEDS.get(expected_name)
        existing_seed_place = find_existing_seed_place(conn, existing_seed_name, representative.get("region_1"))
        enrichment = fetch_enrichment_status(conn, expected_name)
        analysis = build_analysis(
            representative,
            enrichment,
            existing_seed_name=existing_seed_name,
            existing_seed_place=existing_seed_place,
            strategy=strategy,
        )
        payload = build_payload(args, representative, analysis)
        duplicate = existing_duplicate(conn, payload)

        if args.dry_run or not args.write:
            conn.rollback()
            return {
                "status": "DRY_RUN",
                "dry_run": True,
                "write": False,
                "duplicate": duplicate,
                "seed_candidate_id": None,
                **analysis,
            }

        if duplicate:
            conn.rollback()
            return {
                "status": "SKIPPED",
                "dry_run": False,
                "write": True,
                "reason": "DUPLICATE_SEED_CANDIDATE",
                "duplicate": duplicate,
                "seed_candidate_id": None,
                **analysis,
            }

        seed_candidate_id = insert_seed_candidate(conn, payload)
        conn.commit()
        return {
            "status": "INSERTED" if seed_candidate_id else "SKIPPED",
            "dry_run": False,
            "write": True,
            "seed_candidate_id": seed_candidate_id or None,
            **analysis,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create seed candidate staging rows without changing tourism_belt.py.")
    parser.add_argument("--expected-name", required=True)
    parser.add_argument("--strategy", choices=sorted(PROMOTE_STRATEGIES), default="COEXIST_WITH_EXISTING")
    parser.add_argument("--region")
    parser.add_argument("--existing-seed-name")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def print_human(result: dict[str, Any]) -> None:
    print("[Seed Candidate Dry-run]" if result.get("dry_run") else "[Seed Candidate Write]")
    print(f"- status: {result['status']}")
    print(f"- expected_poi_name: {result['expected_poi_name']}")
    print(f"- existing_seed: {result['existing_seed']['name']}")
    print(f"- overlay_candidate: {result['overlay_candidate']['candidate_place_name']}")
    print(f"- strategy: {result['strategy']}")
    print(f"- risk_flags: {result['risk_flags']}")
    print(f"- qa_required: {result['qa_required']}")
    print(f"- duplicate_nearby_risk: {result['duplicate_nearby_risk']}")
    print(f"- existing_seed_distance_km: {result['existing_seed_distance_km']}")
    print(f"- readiness: {result['readiness']}")
    print(f"- readiness_reasons: {result['readiness_reasons']}")
    print(f"- seed_candidate_id: {result.get('seed_candidate_id')}")
    if result.get("duplicate"):
        print(f"- duplicate: {result['duplicate']}")


def main() -> int:
    args = build_parser().parse_args()
    if not args.dry_run and not args.write:
        args.dry_run = True
    try:
        result = create_seed_candidate(args)
    except SeedCandidateError as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
