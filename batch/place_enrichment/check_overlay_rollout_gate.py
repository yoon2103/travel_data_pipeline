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
from batch.place_enrichment.seed_overlay_read_adapter import diagnostics_payload  # noqa: E402


HARD_RISK_FLAGS = {
    "REGION_UNCLEAR",
    "CATEGORY_RISK",
    "LODGING_RISK",
    "PARKING_LOT_RISK",
    "INTERNAL_FACILITY_RISK",
    "SUB_FACILITY_RISK",
}
ROLLOUT_SEED_STATUSES = {"APPROVED", "READY_FOR_PROMOTE", "COEXIST"}
FINAL_GATES = {
    "BLOCKED",
    "QA_REQUIRED",
    "READY_FOR_QA_ONLY",
    "READY_FOR_READ_ONLY_OVERLAY",
    "READY_FOR_LIMITED_ROLLOUT",
    "READY_FOR_MANUAL_PROMOTE",
}


class OverlayRolloutGateError(ValueError):
    pass


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def fetch_representative_bundle(expected_name: str, region: str | None) -> dict[str, Any]:
    where = ["expected_poi_name = %(expected_name)s"]
    params: dict[str, Any] = {"expected_name": expected_name}
    if region:
        where.append("region_1 = %(region)s")
        params["region"] = region

    sql = f"""
        SELECT
            candidate_id,
            expected_poi_name,
            region_1,
            region_2,
            source_type,
            source_name,
            category,
            confidence_score,
            review_status,
            promote_status,
            validation_payload,
            review_payload,
            image_url,
            overview,
            created_at
        FROM representative_poi_candidates
        WHERE {' AND '.join(where)}
        ORDER BY
            CASE WHEN review_status = 'APPROVED' THEN 0 ELSE 1 END,
            confidence_score DESC NULLS LAST,
            candidate_id DESC
    """
    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    representative = next(
        (
            row
            for row in rows
            if row.get("category") not in {"REPRESENTATIVE_IMAGE", "REPRESENTATIVE_OVERVIEW"}
            and row.get("review_status") == "APPROVED"
        ),
        None,
    )
    if representative is None:
        representative = next(
            (
                row
                for row in rows
                if row.get("category") not in {"REPRESENTATIVE_IMAGE", "REPRESENTATIVE_OVERVIEW"}
            ),
            None,
        )

    approved_image = next(
        (
            row
            for row in rows
            if row.get("category") == "REPRESENTATIVE_IMAGE"
            and row.get("review_status") == "APPROVED"
            and row.get("image_url")
        ),
        None,
    )
    image_any = next(
        (row for row in rows if row.get("category") == "REPRESENTATIVE_IMAGE"),
        None,
    )

    approved_overview = next(
        (
            row
            for row in rows
            if row.get("category") == "REPRESENTATIVE_OVERVIEW"
            and row.get("review_status") == "APPROVED"
            and row.get("overview")
        ),
        None,
    )
    overview_any = next(
        (row for row in rows if row.get("category") == "REPRESENTATIVE_OVERVIEW"),
        None,
    )
    return {
        "all_count": len(rows),
        "representative": representative,
        "approved_image": approved_image,
        "image_any": image_any,
        "approved_overview": approved_overview,
        "overview_any": overview_any,
    }


def fetch_seed_candidates(expected_name: str, region: str | None) -> list[dict[str, Any]]:
    where = ["expected_poi_name = %(expected_name)s"]
    params: dict[str, Any] = {"expected_name": expected_name}
    if region:
        where.append("region_1 = %(region)s")
        params["region"] = region
    sql = f"""
        SELECT
            seed_candidate_id,
            region_1,
            region_2,
            expected_poi_name,
            existing_seed_name,
            candidate_place_name,
            representative_candidate_id,
            promote_strategy,
            seed_status,
            review_status,
            risk_flags,
            dry_run_payload,
            created_at,
            updated_at
        FROM seed_candidates
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC, seed_candidate_id DESC
    """
    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def representative_gate(bundle: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    representative = bundle.get("representative")
    approved_image = bundle.get("approved_image")
    approved_overview = bundle.get("approved_overview")

    if not representative:
        blockers.append("REPRESENTATIVE_NOT_FOUND")
        return {
            "status": "BLOCKED",
            "blockers": blockers,
            "warnings": warnings,
            "representative_candidate": None,
            "image_candidate": bundle.get("image_any"),
            "overview_candidate": bundle.get("overview_any"),
        }

    risk_flags = set(as_list((representative.get("validation_payload") or {}).get("risk_flags")))
    hard_flags = sorted(risk_flags & HARD_RISK_FLAGS)

    if representative.get("review_status") != "APPROVED":
        blockers.append("REPRESENTATIVE_NOT_APPROVED")
    if hard_flags:
        blockers.append("HARD_RISK_FLAGS")
    if not approved_image:
        warnings.append("IMAGE_NOT_APPROVED")
    if not approved_overview:
        warnings.append("OVERVIEW_NOT_APPROVED")

    if blockers:
        status = "BLOCKED"
    elif warnings:
        status = "QA_REQUIRED"
    else:
        status = "PASS"

    return {
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "hard_risk_flags": hard_flags,
        "representative_candidate": slim_candidate(representative),
        "image_candidate": slim_candidate(approved_image or bundle.get("image_any")),
        "overview_candidate": slim_candidate(approved_overview or bundle.get("overview_any")),
    }


def seed_gate(seed_rows: list[dict[str, Any]], overlay_payload: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    selected = seed_rows[0] if seed_rows else None

    if not selected:
        warnings.append("NO_SEED_CANDIDATE")
        return {
            "status": "QA_REQUIRED",
            "blockers": blockers,
            "warnings": warnings,
            "seed_candidate": None,
            "duplicate_nearby": None,
        }

    risk_flags = set(as_list(selected.get("risk_flags")))
    hard_flags = sorted(risk_flags & HARD_RISK_FLAGS)
    duplicate = duplicate_info_from_overlay(overlay_payload, selected.get("seed_candidate_id"))
    duplicate_risk = duplicate.get("risk") if duplicate else None

    if selected.get("review_status") != "APPROVED":
        warnings.append("SEED_REVIEW_NOT_APPROVED")
    if selected.get("seed_status") not in ROLLOUT_SEED_STATUSES:
        warnings.append("SEED_STATUS_NOT_READY")
    if hard_flags:
        blockers.append("HARD_RISK_FLAGS")
    if duplicate_risk == "HIGH":
        blockers.append("DUPLICATE_NEARBY_RISK_HIGH")
    elif duplicate_risk == "MEDIUM":
        warnings.append("DUPLICATE_NEARBY_RISK_MEDIUM")

    if blockers:
        status = "BLOCKED"
    elif warnings:
        status = "QA_REQUIRED"
    else:
        status = "PASS"

    return {
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "hard_risk_flags": hard_flags,
        "seed_candidate": {
            "seed_candidate_id": selected.get("seed_candidate_id"),
            "expected_poi_name": selected.get("expected_poi_name"),
            "existing_seed_name": selected.get("existing_seed_name"),
            "candidate_place_name": selected.get("candidate_place_name"),
            "promote_strategy": selected.get("promote_strategy"),
            "seed_status": selected.get("seed_status"),
            "review_status": selected.get("review_status"),
            "risk_flags": as_list(selected.get("risk_flags")),
        },
        "duplicate_nearby": duplicate,
    }


def overlay_gate(overlay_payload: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    eligible_count = overlay_payload.get("eligible_overlay_count", 0)
    blocked_count = overlay_payload.get("blocked_overlay_count", 0)
    fallback_active = overlay_payload.get("fallback_active", False)

    if fallback_active:
        warnings.append("OVERLAY_FALLBACK_ACTIVE")
    if eligible_count <= 0:
        warnings.append("ELIGIBLE_OVERLAY_COUNT_ZERO")
    if blocked_count > 0:
        warnings.append("BLOCKED_OVERLAY_EXISTS")

    for item in overlay_payload.get("blocked_overlay_candidates") or []:
        for blocker in item.get("blockers") or []:
            if blocker not in warnings:
                warnings.append(blocker)

    status = "PASS" if not blockers and not warnings else "QA_REQUIRED"
    return {
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "eligible_overlay_count": eligible_count,
        "blocked_overlay_count": blocked_count,
        "merged_seed_count": overlay_payload.get("merged_seed_count"),
        "fallback_active": fallback_active,
        "fallback_reason": overlay_payload.get("fallback_reason"),
        "fail_closed": {
            "db_write_disabled": overlay_payload.get("db_write") is False,
            "places_unchanged": overlay_payload.get("places_changed") is False,
            "seed_unchanged": overlay_payload.get("seed_changed") is False,
            "engine_unchanged": overlay_payload.get("engine_changed") is False,
            "build_course_not_called": overlay_payload.get("build_course_called") is False,
            "fallback_behavior": overlay_payload.get("fallback_behavior"),
        },
    }


def duplicate_info_from_overlay(
    overlay_payload: dict[str, Any],
    seed_candidate_id: int | None,
) -> dict[str, Any] | None:
    for key in ("accepted_overlay_candidates", "blocked_overlay_candidates"):
        for item in overlay_payload.get(key) or []:
            if item.get("seed_candidate_id") == seed_candidate_id:
                return item.get("duplicate_nearby")
    return None


def slim_candidate(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if not candidate:
        return None
    return {
        "candidate_id": candidate.get("candidate_id"),
        "source_type": candidate.get("source_type"),
        "source_name": candidate.get("source_name"),
        "category": candidate.get("category"),
        "confidence_score": str(candidate.get("confidence_score")),
        "review_status": candidate.get("review_status"),
        "promote_status": candidate.get("promote_status"),
    }


def final_gate(
    representative: dict[str, Any],
    seed: dict[str, Any],
    overlay: dict[str, Any],
) -> str:
    if "BLOCKED" in {representative["status"], seed["status"], overlay["status"]}:
        return "BLOCKED"
    if representative["status"] == "PASS" and seed["status"] == "PASS" and overlay["status"] == "PASS":
        return "READY_FOR_READ_ONLY_OVERLAY"
    if representative["status"] == "PASS" and seed["status"] != "BLOCKED":
        return "READY_FOR_QA_ONLY"
    return "QA_REQUIRED"


def blocker_summary(*gates: dict[str, Any]) -> list[str]:
    summary: list[str] = []
    for gate in gates:
        for key in ("blockers", "warnings"):
            for item in gate.get(key) or []:
                if item not in summary:
                    summary.append(item)
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    overlay_args = argparse.Namespace(
        expected_name=args.expected_name,
        region=args.region,
        strategy="COEXIST_WITH_EXISTING",
        limit=50,
        strict_region_baseline=False,
    )
    overlay_payload = diagnostics_payload(overlay_args)
    rep = representative_gate(fetch_representative_bundle(args.expected_name, args.region))
    seed = seed_gate(fetch_seed_candidates(args.expected_name, args.region), overlay_payload)
    overlay = overlay_gate(overlay_payload)
    final = final_gate(rep, seed, overlay)
    summary = blocker_summary(rep, seed, overlay)

    return {
        "mode": "read-only-rollout-gate-check",
        "db_write": False,
        "places_changed": False,
        "seed_changed": False,
        "engine_changed": False,
        "build_course_called": False,
        "actual_rollout": False,
        "filters": {
            "expected_name": args.expected_name,
            "region": args.region,
        },
        "representative_gate": rep,
        "seed_gate": seed,
        "overlay_gate": overlay,
        "final_rollout_gate": final,
        "blocker_summary": summary,
        "fail_closed": overlay["fail_closed"],
        "next_action": next_action(final, summary),
    }


def next_action(final: str, blockers: list[str]) -> str:
    if "IMAGE_NOT_APPROVED" in blockers:
        return "Approve or reject representative image through visual review before overlay rollout."
    if "SEED_REVIEW_NOT_APPROVED" in blockers or "SEED_STATUS_NOT_READY" in blockers:
        return "Review seed candidate and move it to a rollout-ready status before read-only overlay."
    if final == "READY_FOR_READ_ONLY_OVERLAY":
        return "Run QA-only comparison and smoke tests before any limited rollout."
    if final == "BLOCKED":
        return "Resolve blockers before any rollout."
    return "Continue QA-only diagnostics; actual rollout remains disabled."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check representative overlay rollout gate without writes.")
    parser.add_argument("--expected-name", required=True)
    parser.add_argument("--region")
    parser.add_argument("--json", action="store_true")
    return parser


def print_human(report: dict[str, Any]) -> None:
    print("[Representative Overlay Rollout Gate]")
    print("- mode: read-only-rollout-gate-check")
    print("- db_write: false")
    print("- places_changed: false")
    print("- seed_changed: false")
    print("- engine_changed: false")
    print("- build_course_called: false")
    print(f"- expected_name: {report['filters']['expected_name']}")
    print(f"- representative_gate: {report['representative_gate']['status']}")
    print(f"- seed_gate: {report['seed_gate']['status']}")
    print(f"- overlay_gate: {report['overlay_gate']['status']}")
    print(f"- final_rollout_gate: {report['final_rollout_gate']}")
    print(f"- blocker_summary: {report['blocker_summary']}")
    print(f"- next_action: {report['next_action']}")


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = run(args)
    except Exception as exc:  # noqa: BLE001 - read-only CLI should report diagnostics errors cleanly.
        print(json.dumps({"status": "ERROR", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, default=str, indent=2))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
