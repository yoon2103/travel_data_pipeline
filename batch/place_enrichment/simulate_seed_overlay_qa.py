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
from tourism_belt import TOURISM_BELT  # noqa: E402


PROMOTE_STRATEGIES = {
    "ADDITIVE",
    "COEXIST_WITH_EXISTING",
    "PRIORITY_OVERRIDE",
    "REPRESENTATIVE_ALIAS_ONLY",
}
SIMULATABLE_SEED_STATUSES = {"APPROVED", "NEEDS_REVIEW", "COEXIST", "READY_FOR_PROMOTE"}
HARD_BLOCK_FLAGS = {
    "REGION_UNCLEAR",
    "CATEGORY_RISK",
    "LODGING_RISK",
    "PARKING_LOT_RISK",
    "INTERNAL_FACILITY_RISK",
    "SUB_FACILITY_RISK",
}
GAP_FLAGS = {"IMAGE_MISSING", "OVERVIEW_MISSING"}


class SeedOverlaySimulationError(ValueError):
    pass


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lam / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_baseline_seeds(region: str | None) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    for belt_key, rows in TOURISM_BELT.items():
        if region and region not in {belt_key, "강원", "경북", "충남"}:
            continue
        for row in rows:
            seeds.append(
                {
                    "belt_key": belt_key,
                    "name": row.get("name"),
                    "lat": row.get("lat"),
                    "lon": row.get("lon"),
                    "boost": row.get("boost"),
                    "source": "tourism_belt.py",
                }
            )
    return seeds


def fetch_seed_candidates(args: argparse.Namespace) -> list[dict[str, Any]]:
    where = [
        "sc.seed_status = ANY(%(seed_statuses)s)",
    ]
    params: dict[str, Any] = {
        "seed_statuses": list(SIMULATABLE_SEED_STATUSES),
        "limit": args.limit,
    }
    if args.expected_name:
        where.append("sc.expected_poi_name = %(expected_name)s")
        params["expected_name"] = args.expected_name
    if args.region:
        where.append("sc.region_1 = %(region)s")
        params["region"] = args.region
    sql = f"""
        SELECT
            sc.seed_candidate_id,
            sc.region_1,
            sc.region_2,
            sc.expected_poi_name,
            sc.existing_seed_name,
            sc.representative_candidate_id,
            sc.candidate_place_name,
            sc.promote_strategy,
            sc.seed_status,
            sc.review_status,
            sc.risk_flags,
            sc.source_payload,
            sc.validation_payload,
            sc.dry_run_payload,
            rpc.review_status AS representative_review_status,
            rpc.source_type AS representative_source_type,
            rpc.source_name AS representative_source_name,
            rpc.confidence_score AS representative_confidence_score,
            rpc.latitude AS representative_latitude,
            rpc.longitude AS representative_longitude,
            rpc.category AS representative_category
        FROM seed_candidates sc
        LEFT JOIN representative_poi_candidates rpc
               ON rpc.candidate_id = sc.representative_candidate_id
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


def fetch_place_by_name(name: str | None, region: str | None) -> dict[str, Any] | None:
    if not name:
        return None
    where = ["name = %s"]
    params: list[Any] = [name]
    if region:
        where.append("region_1 = %s")
        params.append(region)
    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT place_id, name, region_1, region_2, latitude, longitude,
                       visit_role, category_id, is_active
                FROM places
                WHERE {' AND '.join(where)}
                ORDER BY is_active DESC, place_id
                LIMIT 1
                """,
                params,
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def normalize_strategy(strategy: str) -> str:
    strategy = strategy.strip().upper()
    if strategy == "COEXIST":
        return "COEXIST_WITH_EXISTING"
    if strategy not in PROMOTE_STRATEGIES and strategy not in {
        "KEEP_EXISTING_ONLY",
        "REPLACE_EXISTING",
    }:
        raise SeedOverlaySimulationError(f"invalid strategy: {strategy}")
    if strategy in {"KEEP_EXISTING_ONLY", "REPLACE_EXISTING"}:
        return strategy
    return strategy


def nearby_risk(distance_km: float | None) -> str:
    if distance_km is None:
        return "UNKNOWN"
    if distance_km <= 1.0:
        return "HIGH"
    if distance_km <= 3.0:
        return "MEDIUM"
    return "LOW"


def overlay_risk_level(flags: set[str], duplicate_risk: str, strategy: str) -> str:
    if flags & HARD_BLOCK_FLAGS:
        return "HIGH"
    if flags & GAP_FLAGS:
        return "HIGH" if strategy in {"PRIORITY_OVERRIDE", "REPLACE_EXISTING"} else "MEDIUM"
    if duplicate_risk == "HIGH":
        return "HIGH" if strategy in {"PRIORITY_OVERRIDE", "REPLACE_EXISTING"} else "MEDIUM"
    if duplicate_risk == "MEDIUM":
        return "MEDIUM"
    return "LOW"


def role_bias(seed_place: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
    baseline_role = seed_place.get("visit_role") if seed_place else None
    candidate_category = candidate.get("representative_category")
    candidate_role = "culture" if candidate_category and "문화" in str(candidate_category) else "spot"
    return {
        "baseline_role": baseline_role,
        "overlay_role_estimate": candidate_role,
        "spot_culture_bias_risk": (
            "MEDIUM"
            if baseline_role in {"spot", "culture"} and candidate_role in {"spot", "culture"}
            else "LOW"
        ),
    }


def simulate_candidate(candidate: dict[str, Any], strategy: str, baseline_seeds: list[dict[str, Any]]) -> dict[str, Any]:
    existing_place = fetch_place_by_name(candidate["existing_seed_name"], candidate["region_1"])
    distance = None
    if (
        existing_place
        and existing_place.get("latitude") is not None
        and existing_place.get("longitude") is not None
        and candidate.get("representative_latitude") is not None
        and candidate.get("representative_longitude") is not None
    ):
        distance = haversine_km(
            float(existing_place["latitude"]),
            float(existing_place["longitude"]),
            float(candidate["representative_latitude"]),
            float(candidate["representative_longitude"]),
        )
    dup_risk = nearby_risk(distance)
    flags = set(candidate.get("risk_flags") or [])
    risk_level = overlay_risk_level(flags, dup_risk, strategy)
    role = role_bias(existing_place, candidate)
    qa_warnings = build_warnings(candidate, flags, dup_risk, strategy, role)
    readiness = readiness_for(candidate, flags, risk_level)

    baseline_match = [
        seed for seed in baseline_seeds
        if seed.get("name") == candidate.get("existing_seed_name")
    ]

    return {
        "expected_poi_name": candidate["expected_poi_name"],
        "strategy": strategy,
        "baseline_seed": {
            "name": candidate["existing_seed_name"],
            "place": existing_place,
            "tourism_belt_matches": baseline_match,
        },
        "overlay_candidate": {
            "seed_candidate_id": candidate["seed_candidate_id"],
            "candidate_place_name": candidate["candidate_place_name"],
            "representative_candidate_id": candidate["representative_candidate_id"],
            "representative_review_status": candidate["representative_review_status"],
            "source_type": candidate["representative_source_type"],
            "source_name": candidate["representative_source_name"],
            "confidence_score": str(candidate["representative_confidence_score"]),
            "latitude": candidate["representative_latitude"],
            "longitude": candidate["representative_longitude"],
        },
        "nearby_seed_distance_km": round(distance, 3) if distance is not None else None,
        "duplicate_nearby_risk": dup_risk,
        "overlay_risk": risk_level,
        "risk_flags": sorted(flags),
        "role_distribution_impact": role,
        "expected_route_impact": {
            "place_count_change": "NONE_EXPECTED_WITHOUT_ENGINE_INTEGRATION",
            "place_count_change_if_applied": "LOW",
            "slot_change_risk": role["spot_culture_bias_risk"],
            "travel_time_impact": "LOW_TO_MEDIUM" if dup_risk in {"MEDIUM", "HIGH"} else "LOW",
            "regional_bias_risk": "MEDIUM" if strategy in {"COEXIST_WITH_EXISTING", "PRIORITY_OVERRIDE"} else "LOW",
            "same_area_density_risk": dup_risk,
        },
        "qa_warnings": qa_warnings,
        "readiness": readiness,
        "recommendation": recommendation(readiness, flags, strategy),
    }


def build_warnings(
    candidate: dict[str, Any],
    flags: set[str],
    dup_risk: str,
    strategy: str,
    role: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    if candidate.get("representative_review_status") != "APPROVED":
        warnings.append("representative candidate is not APPROVED")
    if "IMAGE_MISSING" in flags:
        warnings.append("approved representative image is missing")
    if "OVERVIEW_MISSING" in flags:
        warnings.append("approved representative overview is missing")
    if flags & HARD_BLOCK_FLAGS:
        warnings.append("hard risk flags exist")
    if dup_risk in {"HIGH", "MEDIUM"}:
        warnings.append(f"baseline and overlay seed are nearby: duplicate risk {dup_risk}")
    if role["spot_culture_bias_risk"] != "LOW":
        warnings.append("spot/culture seed density may increase")
    if strategy in {"PRIORITY_OVERRIDE", "REPLACE_EXISTING"}:
        warnings.append("strategy can change recommendation behavior strongly")
    return warnings


def readiness_for(candidate: dict[str, Any], flags: set[str], risk_level: str) -> str:
    if candidate.get("representative_review_status") != "APPROVED":
        return "BLOCKED"
    if flags & HARD_BLOCK_FLAGS:
        return "BLOCKED"
    if flags & GAP_FLAGS:
        return "NOT_READY"
    if risk_level == "HIGH":
        return "REVIEW_REQUIRED"
    return "READY_FOR_QA_SIMULATION"


def recommendation(readiness: str, flags: set[str], strategy: str) -> str:
    if readiness == "BLOCKED":
        return "Do not apply overlay. Resolve hard risks or representative approval first."
    if "IMAGE_MISSING" in flags:
        return "Keep overlay as staging only. Register and approve representative image before any further QA."
    if "OVERVIEW_MISSING" in flags:
        return "Keep overlay as staging only. Approve representative overview before any further QA."
    if strategy in {"PRIORITY_OVERRIDE", "REPLACE_EXISTING"}:
        return "Run baseline-vs-overlay QA before considering priority or replacement."
    return "Proceed to read-only QA comparison; actual engine overlay remains disabled."


def run(args: argparse.Namespace) -> dict[str, Any]:
    args.limit = min(max(args.limit, 1), 500)
    strategy = normalize_strategy(args.strategy)
    baseline = load_baseline_seeds(args.region)
    candidates = fetch_seed_candidates(args)
    if not candidates:
        raise SeedOverlaySimulationError("overlay seed candidate does not exist for the requested filters")

    simulations = [simulate_candidate(candidate, strategy, baseline) for candidate in candidates]
    risk_counts: dict[str, int] = {}
    readiness_counts: dict[str, int] = {}
    for item in simulations:
        risk_counts[item["overlay_risk"]] = risk_counts.get(item["overlay_risk"], 0) + 1
        readiness_counts[item["readiness"]] = readiness_counts.get(item["readiness"], 0) + 1
    return {
        "mode": "dry-run/simulation",
        "db_write": False,
        "places_changed": False,
        "seed_changed": False,
        "engine_changed": False,
        "baseline_source": "tourism_belt.py",
        "overlay_source": "seed_candidates",
        "strategy": strategy,
        "baseline_seed_count_loaded": len(baseline),
        "candidate_count": len(simulations),
        "risk_counts": risk_counts,
        "readiness_counts": readiness_counts,
        "simulations": simulations,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simulate seed overlay QA impact without changing engine or seeds.")
    parser.add_argument("--expected-name")
    parser.add_argument("--strategy", default="COEXIST_WITH_EXISTING")
    parser.add_argument("--region")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    return parser


def print_human(report: dict[str, Any]) -> None:
    print("[Seed Overlay QA Simulation]")
    print("- mode: dry-run/simulation")
    print("- db_write: false")
    print("- places_changed: false")
    print("- seed_changed: false")
    print("- engine_changed: false")
    print(f"- strategy: {report['strategy']}")
    print(f"- baseline_seed_count_loaded: {report['baseline_seed_count_loaded']}")
    print(f"- candidate_count: {report['candidate_count']}")
    print(f"- risk_counts: {report['risk_counts']}")
    print(f"- readiness_counts: {report['readiness_counts']}")
    for item in report["simulations"]:
        print()
        print(f"## {item['expected_poi_name']}")
        print(f"- baseline_seed: {item['baseline_seed']['name']}")
        print(f"- overlay_candidate: {item['overlay_candidate']['candidate_place_name']}")
        print(f"- nearby_seed_distance_km: {item['nearby_seed_distance_km']}")
        print(f"- duplicate_nearby_risk: {item['duplicate_nearby_risk']}")
        print(f"- overlay_risk: {item['overlay_risk']}")
        print(f"- risk_flags: {item['risk_flags']}")
        print(f"- readiness: {item['readiness']}")
        print(f"- qa_warnings: {item['qa_warnings']}")
        print(f"- recommendation: {item['recommendation']}")


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = run(args)
    except SeedOverlaySimulationError as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, default=str, indent=2))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
