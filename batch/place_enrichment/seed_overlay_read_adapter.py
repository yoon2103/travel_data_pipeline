from __future__ import annotations

import argparse
import json
import math
import os
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


MERGE_STRATEGIES = {
    "ADDITIVE",
    "COEXIST_WITH_EXISTING",
    "PRIORITY_OVERRIDE",
    "ALIAS_ONLY",
}
APPROVED_SEED_STATUSES = {"APPROVED", "READY_FOR_PROMOTE", "COEXIST"}
HARD_RISK_FLAGS = {
    "REGION_UNCLEAR",
    "CATEGORY_RISK",
    "LODGING_RISK",
    "PARKING_LOT_RISK",
    "INTERNAL_FACILITY_RISK",
    "SUB_FACILITY_RISK",
}
GAP_FLAGS = {"IMAGE_MISSING", "OVERVIEW_MISSING"}


class SeedOverlayReadAdapterError(ValueError):
    pass


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def normalize_strategy(strategy: str) -> str:
    normalized = strategy.strip().upper()
    if normalized == "COEXIST":
        normalized = "COEXIST_WITH_EXISTING"
    if normalized not in MERGE_STRATEGIES:
        raise SeedOverlayReadAdapterError(f"invalid overlay strategy: {strategy}")
    return normalized


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lam / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_baseline_seeds(region: str | None = None) -> list[dict[str, Any]]:
    """Load hardcoded tourism belt seeds as the immutable baseline view."""
    seeds: list[dict[str, Any]] = []
    for belt_key, rows in TOURISM_BELT.items():
        if region and region not in {belt_key, str(belt_key)}:
            # Keep this conservative. Region-specific overlay diagnostics can still
            # match baseline by existing_seed_name after loading all seeds.
            continue
        for row in rows:
            seeds.append(
                {
                    "name": row.get("name"),
                    "lat": row.get("lat"),
                    "lon": row.get("lon"),
                    "boost": row.get("boost"),
                    "belt_key": belt_key,
                    "source": "tourism_belt.py",
                    "seed_origin": "baseline",
                }
            )
    return seeds


def _fetch_overlay_rows(
    expected_name: str | None,
    region: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    where = ["1=1"]
    params: dict[str, Any] = {"limit": limit}
    if expected_name:
        where.append("sc.expected_poi_name = %(expected_name)s")
        params["expected_name"] = expected_name
    if region:
        where.append("sc.region_1 = %(region)s")
        params["region"] = region

    sql = f"""
        SELECT
            sc.seed_candidate_id,
            sc.region_1,
            sc.region_2,
            sc.expected_poi_name,
            sc.existing_seed_name,
            sc.candidate_place_name,
            sc.promote_strategy,
            sc.seed_status,
            sc.review_status AS seed_review_status,
            sc.risk_flags AS seed_risk_flags,
            sc.source_payload AS seed_source_payload,
            sc.validation_payload AS seed_validation_payload,
            rpc.candidate_id AS representative_candidate_id,
            rpc.source_type AS representative_source_type,
            rpc.source_name AS representative_source_name,
            rpc.source_place_id AS representative_source_place_id,
            rpc.confidence_score AS representative_confidence_score,
            rpc.review_status AS representative_review_status,
            rpc.promote_status AS representative_promote_status,
            rpc.category AS representative_category,
            rpc.latitude AS representative_latitude,
            rpc.longitude AS representative_longitude,
            rpc.validation_payload AS representative_validation_payload,
            img.candidate_id AS image_candidate_id,
            img.review_status AS image_review_status,
            img.image_url AS image_url,
            img.review_payload AS image_review_payload,
            ov.candidate_id AS overview_candidate_id,
            ov.review_status AS overview_review_status,
            ov.overview AS overview,
            ov.review_payload AS overview_review_payload
        FROM seed_candidates sc
        LEFT JOIN representative_poi_candidates rpc
               ON rpc.candidate_id = sc.representative_candidate_id
        LEFT JOIN LATERAL (
            SELECT candidate_id, review_status, image_url, review_payload
            FROM representative_poi_candidates
            WHERE expected_poi_name = sc.expected_poi_name
              AND source_type = 'MANUAL'
              AND category = 'REPRESENTATIVE_IMAGE'
              AND review_status = 'APPROVED'
              AND COALESCE(image_url, '') <> ''
            ORDER BY candidate_id DESC
            LIMIT 1
        ) img ON TRUE
        LEFT JOIN LATERAL (
            SELECT candidate_id, review_status, overview, review_payload
            FROM representative_poi_candidates
            WHERE expected_poi_name = sc.expected_poi_name
              AND source_type = 'MANUAL'
              AND category = 'REPRESENTATIVE_OVERVIEW'
              AND review_status = 'APPROVED'
              AND COALESCE(overview, '') <> ''
            ORDER BY candidate_id DESC
            LIMIT 1
        ) ov ON TRUE
        WHERE {' AND '.join(where)}
        ORDER BY sc.created_at DESC, sc.seed_candidate_id DESC
        LIMIT %(limit)s
    """
    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def load_overlay_candidates(
    expected_name: str | None = None,
    region: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Load overlay candidates and annotate eligibility without mutating data."""
    rows = _fetch_overlay_rows(expected_name, region, limit)
    return [annotate_overlay_candidate(row) for row in rows]


def annotate_overlay_candidate(row: dict[str, Any]) -> dict[str, Any]:
    flags = set(row.get("seed_risk_flags") or [])
    hard_flags = sorted(flags & HARD_RISK_FLAGS)
    gap_flags = sorted(flags & GAP_FLAGS)
    blockers: list[str] = []

    if row.get("seed_review_status") != "APPROVED":
        blockers.append("SEED_REVIEW_NOT_APPROVED")
    if row.get("seed_status") not in APPROVED_SEED_STATUSES:
        blockers.append("SEED_STATUS_NOT_READY")
    if row.get("representative_review_status") != "APPROVED":
        blockers.append("REPRESENTATIVE_NOT_APPROVED")
    if not row.get("image_candidate_id"):
        blockers.append("IMAGE_NOT_APPROVED")
    if not row.get("overview_candidate_id"):
        blockers.append("OVERVIEW_NOT_APPROVED")
    if hard_flags:
        blockers.append("HARD_RISK_FLAGS")

    eligible = not blockers
    overlay_seed = {
        "name": row.get("candidate_place_name"),
        "lat": row.get("representative_latitude"),
        "lon": row.get("representative_longitude"),
        "boost": None,
        "belt_key": row.get("region_2") or row.get("region_1"),
        "source": "seed_candidates",
        "seed_origin": "overlay",
        "expected_poi_name": row.get("expected_poi_name"),
        "existing_seed_name": row.get("existing_seed_name"),
        "seed_candidate_id": row.get("seed_candidate_id"),
        "representative_candidate_id": row.get("representative_candidate_id"),
        "strategy": row.get("promote_strategy"),
    }
    return {
        "seed_candidate_id": row.get("seed_candidate_id"),
        "expected_poi_name": row.get("expected_poi_name"),
        "existing_seed_name": row.get("existing_seed_name"),
        "candidate_place_name": row.get("candidate_place_name"),
        "strategy": row.get("promote_strategy"),
        "seed_status": row.get("seed_status"),
        "seed_review_status": row.get("seed_review_status"),
        "representative_candidate_id": row.get("representative_candidate_id"),
        "representative_review_status": row.get("representative_review_status"),
        "representative_source_type": row.get("representative_source_type"),
        "representative_source_name": row.get("representative_source_name"),
        "representative_confidence_score": str(row.get("representative_confidence_score")),
        "image_candidate_id": row.get("image_candidate_id"),
        "image_review_status": row.get("image_review_status"),
        "overview_candidate_id": row.get("overview_candidate_id"),
        "overview_review_status": row.get("overview_review_status"),
        "risk_flags": sorted(flags),
        "hard_risk_flags": hard_flags,
        "gap_flags": gap_flags,
        "eligible": eligible,
        "blockers": blockers,
        "overlay_seed": overlay_seed,
    }


def find_baseline_seed(seeds: list[dict[str, Any]], name: str | None) -> dict[str, Any] | None:
    if not name:
        return None
    for seed in seeds:
        if seed.get("name") == name:
            return seed
    return None


def duplicate_nearby_risk(
    baseline_seed: dict[str, Any] | None,
    overlay_seed: dict[str, Any],
) -> dict[str, Any]:
    if (
        not baseline_seed
        or baseline_seed.get("lat") is None
        or baseline_seed.get("lon") is None
        or overlay_seed.get("lat") is None
        or overlay_seed.get("lon") is None
    ):
        return {"distance_km": None, "risk": "UNKNOWN"}
    distance = haversine_km(
        float(baseline_seed["lat"]),
        float(baseline_seed["lon"]),
        float(overlay_seed["lat"]),
        float(overlay_seed["lon"]),
    )
    if distance <= 1.0:
        risk = "HIGH"
    elif distance <= 3.0:
        risk = "MEDIUM"
    else:
        risk = "LOW"
    return {"distance_km": round(distance, 3), "risk": risk}


def merge_seed_overlay(
    baseline_seeds: list[dict[str, Any]],
    overlay_candidates: list[dict[str, Any]],
    strategy: str,
) -> dict[str, Any]:
    strategy = normalize_strategy(strategy)
    merged = list(baseline_seeds)
    warnings: list[str] = []
    accepted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for candidate in overlay_candidates:
        overlay_seed = candidate["overlay_seed"]
        baseline_match = find_baseline_seed(baseline_seeds, candidate.get("existing_seed_name"))
        duplicate = duplicate_nearby_risk(baseline_match, overlay_seed)
        diagnostics = {
            **candidate,
            "baseline_seed": baseline_match,
            "duplicate_nearby": duplicate,
        }

        if not candidate["eligible"]:
            blocked.append(diagnostics)
            warnings.append(
                f"{candidate['expected_poi_name']} blocked: {', '.join(candidate['blockers'])}"
            )
            continue

        if duplicate["risk"] in {"HIGH", "MEDIUM"}:
            warnings.append(
                f"{candidate['expected_poi_name']} duplicate nearby risk {duplicate['risk']} "
                f"against {candidate.get('existing_seed_name')}"
            )

        if strategy in {"ADDITIVE", "COEXIST_WITH_EXISTING"}:
            merged.append(overlay_seed)
        elif strategy == "PRIORITY_OVERRIDE":
            merged = [
                seed
                for seed in merged
                if seed.get("name") != candidate.get("existing_seed_name")
            ]
            merged.append({**overlay_seed, "priority_override": True})
        elif strategy == "ALIAS_ONLY":
            # Alias-only does not alter the seed list used by recommendations.
            overlay_seed = {**overlay_seed, "alias_only": True}

        accepted.append(diagnostics)

    return {
        "strategy": strategy,
        "baseline_seed_count": len(baseline_seeds),
        "eligible_overlay_count": len(accepted),
        "blocked_overlay_count": len(blocked),
        "merged_seed_count": len(merged),
        "baseline_seeds": baseline_seeds,
        "accepted_overlay_candidates": accepted,
        "blocked_overlay_candidates": blocked,
        "merged_seed_view": merged,
        "overlay_warnings": warnings,
    }


def diagnostics_payload(args: argparse.Namespace) -> dict[str, Any]:
    strategy = normalize_strategy(args.strategy)
    read_only_flag = env_bool("REPRESENTATIVE_OVERLAY_READ_ONLY", True)
    enabled_flag = env_bool("REPRESENTATIVE_OVERLAY_ENABLED", False)
    qa_only_flag = env_bool("REPRESENTATIVE_OVERLAY_QA_ONLY", True)

    baseline_region = args.region if args.strict_region_baseline else None
    baseline = load_baseline_seeds(baseline_region)
    fallback_reason = None
    if not read_only_flag:
        overlays = []
        fallback_reason = "REPRESENTATIVE_OVERLAY_READ_ONLY=false"
    else:
        try:
            overlays = load_overlay_candidates(args.expected_name, args.region, args.limit)
        except Exception as exc:  # noqa: BLE001 - diagnostics adapter must fail closed to baseline.
            overlays = []
            fallback_reason = f"overlay_load_failed: {exc}"
    merged = merge_seed_overlay(baseline, overlays, strategy)
    return {
        "mode": "read-only-overlay-diagnostics",
        "db_write": False,
        "places_changed": False,
        "seed_changed": False,
        "engine_changed": False,
        "build_course_called": False,
        "feature_flags": {
            "REPRESENTATIVE_OVERLAY_READ_ONLY": read_only_flag,
            "REPRESENTATIVE_OVERLAY_ENABLED": enabled_flag,
            "REPRESENTATIVE_OVERLAY_QA_ONLY": qa_only_flag,
            "effective_behavior": "diagnostics_only_baseline_fallback",
        },
        "fallback_active": fallback_reason is not None,
        "fallback_reason": fallback_reason,
        "filters": {
            "expected_name": args.expected_name,
            "region": args.region,
            "limit": args.limit,
        },
        "baseline_source": "tourism_belt.py",
        "overlay_source": "seed_candidates + representative_poi_candidates",
        **merged,
        "fallback_behavior": "baseline_only_on_overlay_error_or_ineligible_candidate",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only baseline tourism_belt + approved seed overlay diagnostics adapter."
    )
    parser.add_argument("--expected-name")
    parser.add_argument("--region")
    parser.add_argument("--strategy", default=os.getenv("REPRESENTATIVE_OVERLAY_STRATEGY", "COEXIST_WITH_EXISTING"))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--strict-region-baseline",
        action="store_true",
        help="Filter tourism_belt baseline by belt key. Default loads all baseline seeds for safer name diagnostics.",
    )
    return parser


def print_human(payload: dict[str, Any]) -> None:
    print("[Seed Overlay Read Adapter Diagnostics]")
    print("- mode: read-only-overlay-diagnostics")
    print("- db_write: false")
    print("- places_changed: false")
    print("- seed_changed: false")
    print("- engine_changed: false")
    print("- build_course_called: false")
    print(f"- strategy: {payload['strategy']}")
    print(f"- baseline_seed_count: {payload['baseline_seed_count']}")
    print(f"- eligible_overlay_count: {payload['eligible_overlay_count']}")
    print(f"- blocked_overlay_count: {payload['blocked_overlay_count']}")
    print(f"- merged_seed_count: {payload['merged_seed_count']}")
    if payload["overlay_warnings"]:
        print("- overlay_warnings:")
        for warning in payload["overlay_warnings"]:
            print(f"  - {warning}")
    for candidate in payload["accepted_overlay_candidates"]:
        print()
        print(f"## accepted: {candidate['expected_poi_name']}")
        print(f"- overlay_seed: {candidate['candidate_place_name']}")
        print(f"- duplicate_nearby: {candidate['duplicate_nearby']}")
    for candidate in payload["blocked_overlay_candidates"]:
        print()
        print(f"## blocked: {candidate['expected_poi_name']}")
        print(f"- overlay_seed: {candidate['candidate_place_name']}")
        print(f"- blockers: {candidate['blockers']}")
        print(f"- duplicate_nearby: {candidate['duplicate_nearby']}")


def main() -> int:
    args = build_parser().parse_args()
    args.limit = min(max(args.limit, 1), 500)
    try:
        payload = diagnostics_payload(args)
    except SeedOverlayReadAdapterError as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, default=str, indent=2))
    else:
        print_human(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
