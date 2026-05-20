from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any
from datetime import datetime

import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import db_client  # noqa: E402
from batch.external.common import finish_run, log_step  # noqa: E402
from batch.external.stage_external_candidates import build_candidates  # noqa: E402


APPROVED_ONLY_PROMOTE_TODO = """
SAFETY TODO:
  External candidate promotion must move to an approved-only gate before
  production write mode is expanded.

  Required future guards:
    - staging_external_places.qa_status = 'PASS'
    - staging_external_places.promotion_status = 'approved'
    - staging_external_places.business_safety_status = 'safe'
    - duplicate/manual review policy passed
    - required fields exist: source, external_id, name, region, lat/lng, visit_role
    - BLOCK_MISSING_IMAGE is cleared only when:
        image_review_status = 'approved'
        image_url exists
        image_license_note exists

  Current script still reads staging_places for backward compatibility.
  Treat --write as an exceptional operator action, not the default workflow.
  Legacy write requires EXTERNAL_PROMOTE_UNLOCK=true and an approval file token.
"""

PROMOTE_UNLOCK_TOKEN = "APPROVED_ONLY_EXTERNAL_PROMOTE_UNLOCK"

BLOCK_REASON_MAP = {
    "qa_status_not_pass": "BLOCK_QA_FAIL",
    "promotion_status_not_approved": "BLOCK_REVIEW_PENDING",
    "business_safety_not_safe": "BLOCK_BUSINESS_STATUS",
    "duplicate_review_not_cleared": "BLOCK_DUPLICATE_RISK",
    "missing_source": "BLOCK_REQUIRED_FIELD",
    "missing_external_id": "BLOCK_REQUIRED_FIELD",
    "missing_name": "BLOCK_REQUIRED_FIELD",
    "missing_region": "BLOCK_REQUIRED_FIELD",
    "missing_latitude": "BLOCK_MISSING_COORDINATE",
    "missing_longitude": "BLOCK_MISSING_COORDINATE",
    "missing_visit_role": "BLOCK_INVALID_ROLE",
    "unsupported_source": "BLOCK_UNSUPPORTED_SOURCE",
    "invalid_visit_role": "BLOCK_INVALID_ROLE",
}

REVIEW_BLOCK_REASON_MAP = {
    "BLOCK_DUPLICATE_RISK": "BLOCK_DUPLICATE_RISK",
    "BLOCK_MISSING_COORDINATE": "BLOCK_MISSING_COORDINATE",
    "BLOCK_CATEGORY_RISK": "BLOCK_CATEGORY_RISK",
    "BLOCK_MISSING_IMAGE": "BLOCK_MISSING_IMAGE",
    "BLOCK_CLOSED_BUSINESS": "BLOCK_BUSINESS_STATUS",
}


def _promote_unlock_state() -> dict[str, Any]:
    unlock_file = os.environ.get("EXTERNAL_PROMOTE_UNLOCK_FILE") or str(ROOT_DIR / ".external_promote_unlock")
    env_ok = os.environ.get("EXTERNAL_PROMOTE_UNLOCK") == "true"
    file_path = Path(unlock_file)
    file_exists = file_path.exists()
    token_ok = False
    if file_exists:
        token_ok = file_path.read_text(encoding="utf-8").strip() == PROMOTE_UNLOCK_TOKEN
    return {
        "env_required": "EXTERNAL_PROMOTE_UNLOCK=true",
        "env_ok": env_ok,
        "approval_file": str(file_path),
        "file_exists": file_exists,
        "token_ok": token_ok,
        "unlocked": env_ok and file_exists and token_ok,
    }


def _load_image_review_approvals(path: str | None) -> set[str]:
    if not path:
        return set()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    approved: set[str] = set()
    for row in payload.get("review_rows") or []:
        has_staging_image_approval = (
            row.get("image_review_status") == "approved"
            and bool(row.get("image_link"))
            and bool(row.get("image_license_note"))
        )
        if has_staging_image_approval:
            name = str(row.get("place_name") or "").strip()
            if name:
                approved.add(name)
    rehearsal = payload.get("persistence_rehearsal") or {}
    rehearsal_staging_payload = rehearsal.get("staging_external_places_update_payload") or {}
    if (
        rehearsal_staging_payload.get("image_review_status") == "approved"
        and rehearsal_staging_payload.get("image_url")
        and rehearsal_staging_payload.get("image_license_note")
    ):
        name = str(rehearsal.get("candidate") or "").strip()
        if name:
            approved.add(name)
    return approved


def _apply_image_review_override(blocked: list[dict[str, Any]], approved_names: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not approved_names:
        return [], blocked
    adjusted_approved: list[dict[str, Any]] = []
    still_blocked: list[dict[str, Any]] = []
    for item in blocked:
        reasons = list(item.get("block_reasons") or [])
        name = str(item.get("name") or "").strip()
        if name in approved_names and reasons == ["BLOCK_MISSING_IMAGE"]:
            adjusted_approved.append(
                {
                    **item,
                    "approved_only_decision": "WOULD_PROMOTE_WITH_IMAGE_REVIEW",
                    "block_reasons": [],
                    "recommended_operator_action": "preview_only_no_write",
                    "image_review_override": True,
                }
            )
        else:
            still_blocked.append(item)
    return adjusted_approved, still_blocked


def _canonical_block_reasons(errors: list[str]) -> list[str]:
    mapped = [BLOCK_REASON_MAP.get(error, error) for error in errors]
    return sorted(set(mapped))


def _table_exists(conn, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = %s
            )
            """,
            (table_name,),
        )
        return bool(cur.fetchone()[0])


def _approved_precondition_errors(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if row.get("qa_status") != "PASS":
        errors.append("qa_status_not_pass")
    if row.get("promotion_status") != "approved":
        errors.append("promotion_status_not_approved")
    if row.get("business_safety_status") != "safe":
        errors.append("business_safety_not_safe")
    if row.get("duplicate_review_status") not in {"unique", "needs_manual_review"}:
        errors.append("duplicate_review_not_cleared")
    for field in ("source", "external_id", "name", "region", "latitude", "longitude", "visit_role"):
        if row.get(field) in (None, ""):
            errors.append(f"missing_{field}")
    if row.get("source") not in {"kakao", "naver"}:
        errors.append("unsupported_source")
    if row.get("visit_role") not in {"cafe", "meal", "culture", "spot"}:
        errors.append("invalid_visit_role")
    return errors


def approved_only_dry_run(run_id: str, region: str | None) -> dict:
    conn = db_client.get_connection()
    try:
        if not _table_exists(conn, "staging_external_places"):
            return {
                "run_id": run_id,
                "write": False,
                "blocked": "staging_external_places table does not exist; migration is still draft",
                "approved_candidate_count": 0,
            }
        sql = """
            SELECT *
            FROM staging_external_places
            WHERE run_id = %s
        """
        params: list[Any] = [run_id]
        if region:
            sql += " AND region = %s"
            params.append(region)
        sql += " ORDER BY id"
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = list(cur.fetchall())
        approved: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for row in rows:
            row_dict = dict(row)
            errors = _approved_precondition_errors(row_dict)
            payload = {
                "id": row_dict.get("id"),
                "source": row_dict.get("source"),
                "external_id": row_dict.get("external_id"),
                "name": row_dict.get("name"),
                "region": row_dict.get("region"),
                "visit_role": row_dict.get("visit_role"),
                "errors": errors,
                "block_reasons": _canonical_block_reasons(errors),
            }
            if errors:
                blocked.append(payload)
            else:
                approved.append(payload)
        return {
            "run_id": run_id,
            "write": False,
            "checked_count": len(rows),
            "approved_candidate_count": len(approved),
            "blocked_candidate_count": len(blocked),
            "blocked_reason_counts": _count_block_reasons(blocked),
            "approved_candidates": approved,
            "blocked_candidates": blocked[:50],
            "safety_warning": "approved-only dry-run only; no production places write",
        }
    finally:
        conn.close()


def _count_block_reasons(blocked: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in blocked:
        for reason in item.get("block_reasons") or []:
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _candidate_key(candidate: dict[str, Any]) -> str:
    return f"{candidate.get('source') or ''}:{candidate.get('external_id') or ''}"


def _legacy_preview(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": row.get("external_source"),
        "external_id": row.get("external_id"),
        "name": row.get("name"),
        "region": row.get("region_1"),
        "category": row.get("category_id"),
        "visit_role": row.get("visit_role"),
        "legacy_decision": "WOULD_PROMOTE",
        "approved_only_decision": "UNKNOWN",
        "block_reasons": [],
        "recommended_operator_action": "compare_against_approved_only_gate",
    }


def _operator_action(block_reasons: list[str], *, approved: bool = False) -> str:
    if approved:
        return "preview_only_no_write"
    hard_reject = {"BLOCK_MISSING_COORDINATE", "BLOCK_BUSINESS_STATUS", "BLOCK_INVALID_ROLE", "BLOCK_UNSUPPORTED_SOURCE"}
    if any(reason in hard_reject for reason in block_reasons):
        return "reject_or_fix_source_before_review"
    if "BLOCK_DUPLICATE_RISK" in block_reasons:
        return "manual_duplicate_review_required"
    if "BLOCK_MISSING_IMAGE" in block_reasons:
        return "manual_quality_review_required"
    if "BLOCK_REVIEW_PENDING" in block_reasons:
        return "reviewer_approval_required"
    return "manual_review_required"


def _simulate_review_transition(candidate: dict[str, Any]) -> dict[str, Any]:
    initial = "PENDING_REVIEW"
    if candidate.get("review_decision") == "APPROVE_CANDIDATE":
        review_state = "APPROVED"
        final_state = "PROMOTE_ELIGIBLE"
        block_reasons: list[str] = []
    elif candidate.get("review_decision") == "BLOCK":
        review_state = "REJECTED"
        final_state = "BLOCKED"
        block_reasons = [REVIEW_BLOCK_REASON_MAP.get(reason, reason) for reason in candidate.get("block_reasons") or []]
    else:
        review_state = "REVIEW_REQUIRED"
        final_state = "BLOCKED"
        block_reasons = [REVIEW_BLOCK_REASON_MAP.get(reason, reason) for reason in candidate.get("block_reasons") or []]
        if not block_reasons:
            block_reasons = ["BLOCK_REVIEW_PENDING"]
    return {
        "clean_external_place_id": candidate.get("clean_external_place_id"),
        "source": candidate.get("source"),
        "external_id": candidate.get("external_id"),
        "name": candidate.get("name"),
        "region": candidate.get("region"),
        "category": candidate.get("category"),
        "visit_role": candidate.get("visit_role"),
        "initial_state": initial,
        "review_state": review_state,
        "final_state": final_state,
        "block_reasons": sorted(set(block_reasons)),
    }


def approved_only_rehearsal(run_id: str, region: str | None, limit: int, visit_role: str | None = None) -> dict:
    staged = build_candidates(run_id, region, limit, visit_role)
    transitions = [_simulate_review_transition(candidate) for candidate in staged["candidates"]]
    final_candidates = [item for item in transitions if item["final_state"] == "PROMOTE_ELIGIBLE"]
    blocked = [item for item in transitions if item["final_state"] != "PROMOTE_ELIGIBLE"]
    reason_counts = _count_block_reasons(blocked)
    return {
        "run_id": run_id,
        "region": region,
        "visit_role": visit_role,
        "write": False,
        "mode": "approved_only_rehearsal",
        "source": "clean_external_places simulation",
        "candidate_summary": staged["summary"],
        "approve_candidate_count": len(final_candidates),
        "blocked_candidate_count": len(blocked),
        "duplicate_blocked_count": reason_counts.get("BLOCK_DUPLICATE_RISK", 0),
        "business_safety_blocked_count": reason_counts.get("BLOCK_BUSINESS_STATUS", 0),
        "missing_image_blocked_count": reason_counts.get("BLOCK_MISSING_IMAGE", 0),
        "missing_coordinate_blocked_count": reason_counts.get("BLOCK_MISSING_COORDINATE", 0),
        "invalid_role_blocked_count": reason_counts.get("BLOCK_INVALID_ROLE", 0),
        "blocked_reason_counts": reason_counts,
        "reviewer_state_transitions": transitions[:100],
        "final_promote_candidate_preview": final_candidates[:50],
        "safety_summary": {
            "production_places_write": False,
            "migration_required_for_persistence": True,
            "legacy_promote_used": False,
        },
    }


def _approved_shadow_preview(run_id: str, region: str | None, limit: int, visit_role: str | None = None) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    conn = db_client.get_connection()
    try:
        has_staging_external = _table_exists(conn, "staging_external_places")
    finally:
        conn.close()

    if has_staging_external:
        result = approved_only_dry_run(run_id, region)
        approved = []
        for item in result.get("approved_candidates") or []:
            approved.append(
                {
                    **item,
                    "approved_only_decision": "WOULD_PROMOTE",
                    "recommended_operator_action": "preview_only_no_write",
                }
            )
        blocked = []
        for item in result.get("blocked_candidates") or []:
            reasons = item.get("block_reasons") or _canonical_block_reasons(item.get("errors") or [])
            blocked.append(
                {
                    **item,
                    "approved_only_decision": "BLOCKED",
                    "block_reasons": reasons,
                    "recommended_operator_action": _operator_action(reasons),
                }
            )
        return "staging_external_places", approved, blocked

    rehearsal = approved_only_rehearsal(run_id, region, limit, visit_role)
    approved = []
    blocked = []
    for item in rehearsal.get("reviewer_state_transitions") or []:
        reasons = item.get("block_reasons") or []
        payload = {
            "source": item.get("source"),
            "external_id": item.get("external_id"),
            "name": item.get("name"),
            "region": item.get("region"),
            "category": item.get("category"),
            "visit_role": item.get("visit_role"),
            "approved_only_decision": "WOULD_PROMOTE" if item.get("final_state") == "PROMOTE_ELIGIBLE" else "BLOCKED",
            "block_reasons": reasons,
            "recommended_operator_action": _operator_action(reasons, approved=item.get("final_state") == "PROMOTE_ELIGIBLE"),
        }
        if item.get("final_state") == "PROMOTE_ELIGIBLE":
            approved.append(payload)
        else:
            blocked.append(payload)
    return "clean_external_places simulation", approved, blocked


def shadow_mode(run_id: str, region: str | None, limit: int, visit_role: str | None = None, image_review_report: str | None = None) -> dict:
    conn = db_client.get_connection()
    try:
        legacy_rows = _load_staging(conn, run_id, region, visit_role)[:limit]
    finally:
        conn.close()

    legacy_candidates = [_legacy_preview(dict(row)) for row in legacy_rows]
    approved_source, approved_candidates, blocked_candidates = _approved_shadow_preview(run_id, region, limit, visit_role)
    image_review_approved_names = _load_image_review_approvals(image_review_report)
    image_adjusted_candidates, image_still_blocked = _apply_image_review_override(blocked_candidates, image_review_approved_names)
    approved_candidates_for_counts = approved_candidates + image_adjusted_candidates

    legacy_by_key = {_candidate_key(item): item for item in legacy_candidates if _candidate_key(item) != ":"}
    approved_by_key = {_candidate_key(item): item for item in approved_candidates_for_counts if _candidate_key(item) != ":"}
    blocked_by_key = {_candidate_key(item): item for item in image_still_blocked if _candidate_key(item) != ":"}

    legacy_only: list[dict[str, Any]] = []
    for key, item in legacy_by_key.items():
        if key in approved_by_key:
            continue
        blocked = blocked_by_key.get(key)
        reasons = blocked.get("block_reasons", ["BLOCK_REVIEW_PENDING"]) if blocked else ["BLOCK_REVIEW_PENDING"]
        legacy_only.append(
            {
                **item,
                "approved_only_decision": "BLOCKED",
                "block_reasons": reasons,
                "recommended_operator_action": _operator_action(reasons),
            }
        )

    approved_only = []
    for key, item in approved_by_key.items():
        if key not in legacy_by_key:
            approved_only.append({**item, "legacy_decision": "NOT_IN_LEGACY_PREVIEW"})

    false_positive_risk = []
    for item in legacy_only:
        reasons = set(item.get("block_reasons") or [])
        if reasons & {
            "BLOCK_DUPLICATE_RISK",
            "BLOCK_BUSINESS_STATUS",
            "BLOCK_MISSING_COORDINATE",
            "BLOCK_INVALID_ROLE",
            "BLOCK_UNSUPPORTED_SOURCE",
            "BLOCK_REVIEW_PENDING",
            "BLOCK_REQUIRED_FIELD",
        }:
            false_positive_risk.append(item)

    false_negative_risk = []
    for item in image_still_blocked:
        reasons = set(item.get("block_reasons") or [])
        if reasons and reasons <= {"BLOCK_MISSING_IMAGE"}:
            false_negative_risk.append(item)
        elif "BLOCK_DUPLICATE_RISK" in reasons and len(reasons) == 1:
            false_negative_risk.append(item)

    shadow_blocked_for_counts = legacy_only if legacy_only else image_still_blocked

    return {
        "run_id": run_id,
        "region": region,
        "visit_role": visit_role,
        "write": False,
        "mode": "shadow_mode",
        "approved_only_source": approved_source,
        "legacy_candidate_count": len(legacy_candidates),
        "approved_eligible_count": len(approved_candidates),
        "image_review_adjusted_eligible_count": len(approved_candidates_for_counts),
        "image_approved_candidate_count": len(image_adjusted_candidates),
        "legacy_only_count": len(legacy_only),
        "approved_only_count": len(approved_only),
        "blocked_reason_counts": _count_block_reasons(shadow_blocked_for_counts),
        "legacy_only_candidates": legacy_only[:50],
        "approved_only_candidates": approved_only[:50],
        "false_positive_risk": false_positive_risk[:50],
        "false_negative_risk": false_negative_risk[:50],
        "image_approved_candidates": image_adjusted_candidates[:50],
        "still_blocked_candidates": image_still_blocked[:50],
        "remaining_block_reasons": _count_block_reasons(image_still_blocked),
        "image_review_report": image_review_report,
        "operator_report": {
            "summary": "write disabled; compare legacy would-promote candidates against approved-only gate",
            "required_action": "review legacy_only_candidates and false_positive_risk before any migration/promote cutover",
        },
        "safety_summary": {
            "production_places_write": False,
            "migration_executed": False,
            "legacy_promote_executed": False,
            "raw_overwrite": False,
            "full_reload": False,
        },
    }


SHADOW_REPORT_FIELDS = [
    "section",
    "name",
    "source",
    "category",
    "region",
    "visit_role",
    "legacy_decision",
    "approved_only_decision",
    "block_reasons",
    "recommended_operator_action",
]


def _safe_filename_part(value: str | None) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value or "all"))
    return text.strip("_") or "all"


def _shadow_report_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in ("legacy_only_candidates", "approved_only_candidates", "false_positive_risk", "false_negative_risk"):
        for item in result.get(section) or []:
            rows.append(
                {
                    "section": section,
                    "name": item.get("name"),
                    "source": item.get("source"),
                    "category": item.get("category"),
                    "region": item.get("region"),
                    "visit_role": item.get("visit_role"),
                    "legacy_decision": item.get("legacy_decision"),
                    "approved_only_decision": item.get("approved_only_decision"),
                    "block_reasons": "|".join(item.get("block_reasons") or []),
                    "recommended_operator_action": item.get("recommended_operator_action"),
                }
            )
    for item in result.get("image_approved_candidates") or []:
        rows.append(
            {
                "section": "image_approved_candidates",
                "name": item.get("name"),
                "source": item.get("source"),
                "category": item.get("category"),
                "region": item.get("region"),
                "visit_role": item.get("visit_role"),
                "legacy_decision": item.get("legacy_decision"),
                "approved_only_decision": item.get("approved_only_decision"),
                "block_reasons": "|".join(item.get("block_reasons") or []),
                "recommended_operator_action": item.get("recommended_operator_action"),
            }
        )
    return rows


def _markdown_candidate_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No candidates._"
    lines = [
        "| section | name | source | category | region | legacy | approved-only | block reasons | action |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {section} | {name} | {source} | {category} | {region} | {legacy} | {approved} | {reasons} | {action} |".format(
                section=str(row.get("section") or "").replace("|", "/"),
                name=str(row.get("name") or "").replace("|", "/"),
                source=str(row.get("source") or "").replace("|", "/"),
                category=str(row.get("category") or "").replace("|", "/"),
                region=str(row.get("region") or "").replace("|", "/"),
                legacy=str(row.get("legacy_decision") or "").replace("|", "/"),
                approved=str(row.get("approved_only_decision") or "").replace("|", "/"),
                reasons=str(row.get("block_reasons") or "").replace("|", ", "),
                action=str(row.get("recommended_operator_action") or "").replace("|", "/"),
            )
        )
    return "\n".join(lines)


def write_shadow_report(result: dict[str, Any], output_dir: str) -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = "shadow_mode_{run_id}_{region}_{role}_{timestamp}".format(
        run_id=_safe_filename_part(result.get("run_id")),
        region=_safe_filename_part(result.get("region")),
        role=_safe_filename_part(result.get("visit_role")),
        timestamp=timestamp,
    )
    json_path = out / f"{stem}.json"
    csv_path = out / f"{stem}.csv"
    md_path = out / f"{stem}.md"

    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    rows = _shadow_report_rows(result)
    with csv_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=SHADOW_REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    blocked_counts = result.get("blocked_reason_counts") or {}
    blocked_lines = "\n".join(f"- {key}: {value}" for key, value in blocked_counts.items()) or "- none"
    md = f"""# Shadow Mode Report

## Summary

- run_id: `{result.get("run_id")}`
- region: `{result.get("region") or "ALL"}`
- visit_role: `{result.get("visit_role") or "ALL"}`
- approved_only_source: `{result.get("approved_only_source")}`
- legacy_candidate_count: {result.get("legacy_candidate_count")}
- approved_eligible_count: {result.get("approved_eligible_count")}
- image_review_adjusted_eligible_count: {result.get("image_review_adjusted_eligible_count")}
- image_approved_candidate_count: {result.get("image_approved_candidate_count")}
- legacy_only_count: {result.get("legacy_only_count")}
- approved_only_count: {result.get("approved_only_count")}
- false_positive_risk_count: {len(result.get("false_positive_risk") or [])}
- false_negative_risk_count: {len(result.get("false_negative_risk") or [])}

## Blocked Reason Counts

{blocked_lines}

## Candidate Review Table

{_markdown_candidate_table(rows)}

## Operator Notes

- `BLOCK_DUPLICATE_RISK`: 기존 places와 중복 가능성. 자동 approve 금지.
- `BLOCK_MISSING_IMAGE`: 즉시 reject는 아니지만 품질 review 필요.
- `REVIEW_REQUIRED`: 사람이 판단해야 하며 자동 promote 금지.
- `PROMOTE_ELIGIBLE`: final preview 확인 전 write 금지.
- `--allow-promote`는 일반 운영 옵션이 아니라 legacy escape hatch.

## Safety

- production places write: false
- migration executed: false
- raw overwrite: false
- full reload: false
"""
    md_path.write_text(md, encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def _load_staging(conn, run_id: str, region: str | None, visit_role: str | None = None) -> list[dict]:
    sql = """
        SELECT *
        FROM staging_places
        WHERE run_id = %s
          AND source = 'external'
          AND external_source IN ('kakao', 'naver')
          AND external_id IS NOT NULL
    """
    params: list = [run_id]
    if region:
        sql += " AND region_1 = %s"
        params.append(region)
    if visit_role:
        sql += " AND visit_role = %s"
        params.append(visit_role)
    sql += " ORDER BY id"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def _snapshot_existing(conn, run_id: str, row: dict) -> int:
    id_column = "kakao_place_id" if row["external_source"] == "kakao" else "naver_place_id"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM places WHERE {id_column} = %s LIMIT 1", (row["external_id"],))
        existing = cur.fetchone()
        if not existing:
            return 0
        cur.execute(
            """
            INSERT INTO place_update_snapshots (
                run_id, place_id, tourapi_content_id, before_payload
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (run_id, place_id) DO NOTHING
            """,
            (
                run_id,
                existing["place_id"],
                existing["tourapi_content_id"],
                psycopg2.extras.Json(json.loads(json.dumps(dict(existing), ensure_ascii=False, default=str))),
            ),
        )
        return cur.rowcount


def _upsert_external(conn, row: dict) -> int:
    if row["external_source"] == "kakao":
        external_column = "kakao_place_id"
        conflict = "ON CONFLICT (kakao_place_id) WHERE kakao_place_id IS NOT NULL"
    else:
        external_column = "naver_place_id"
        conflict = "ON CONFLICT (naver_place_id) WHERE naver_place_id IS NOT NULL"

    sql = f"""
        INSERT INTO places (
            name, category_id, region_1, region_2, latitude, longitude, overview,
            first_image_url, first_image_thumb_url, ai_summary, ai_tags, embedding,
            visit_role, estimated_duration, visit_time_slot,
            ai_validation_status, ai_validation_errors,
            data_source, {external_column}, source_confidence, indoor_outdoor,
            is_active, synced_at
        )
        VALUES (
            %(name)s, %(category_id)s, %(region_1)s, %(region_2)s, %(latitude)s, %(longitude)s, %(overview)s,
            %(first_image_url)s, %(first_image_thumb_url)s, %(ai_summary)s, %(ai_tags)s, NULL,
            %(visit_role)s, %(estimated_duration)s, %(visit_time_slot)s,
            %(ai_validation_status)s, %(ai_validation_errors)s,
            'external', %(external_id)s, 0.85, %(indoor_outdoor)s,
            TRUE, NOW()
        )
        {conflict}
        DO UPDATE SET
            name = EXCLUDED.name,
            category_id = EXCLUDED.category_id,
            region_1 = EXCLUDED.region_1,
            region_2 = EXCLUDED.region_2,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            overview = COALESCE(NULLIF(EXCLUDED.overview, ''), places.overview),
            ai_summary = CASE
                WHEN places.data_source = 'external' THEN EXCLUDED.ai_summary
                ELSE COALESCE(EXCLUDED.ai_summary, places.ai_summary)
            END,
            ai_tags = CASE
                WHEN places.data_source = 'external' THEN EXCLUDED.ai_tags
                ELSE COALESCE(EXCLUDED.ai_tags, places.ai_tags)
            END,
            visit_role = COALESCE(EXCLUDED.visit_role, places.visit_role),
            estimated_duration = COALESCE(EXCLUDED.estimated_duration, places.estimated_duration),
            visit_time_slot = COALESCE(EXCLUDED.visit_time_slot, places.visit_time_slot),
            ai_validation_status = EXCLUDED.ai_validation_status,
            ai_validation_errors = EXCLUDED.ai_validation_errors,
            data_source = 'external',
            source_confidence = GREATEST(COALESCE(places.source_confidence, 0), 0.85),
            indoor_outdoor = COALESCE(EXCLUDED.indoor_outdoor, places.indoor_outdoor),
            is_active = TRUE,
            synced_at = NOW(),
            updated_at = NOW()
        RETURNING place_id
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            {
                "name": row["name"],
                "category_id": row["category_id"],
                "region_1": row["region_1"],
                "region_2": row["region_2"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "overview": row["overview"],
                "first_image_url": row.get("first_image_url"),
                "first_image_thumb_url": row.get("first_image_thumb_url"),
                "ai_summary": row["ai_summary"],
                "ai_tags": psycopg2.extras.Json(row["ai_tags"]),
                "visit_role": row["visit_role"],
                "estimated_duration": row["estimated_duration"],
                "visit_time_slot": row["visit_time_slot"],
                "ai_validation_status": row["ai_validation_status"],
                "ai_validation_errors": psycopg2.extras.Json(row["ai_validation_errors"]),
                "external_id": row["external_id"],
                "indoor_outdoor": row.get("indoor_outdoor"),
            },
        )
        cur.fetchone()
        return 1


def promote(run_id: str, region: str | None, qa_passed: bool, write: bool) -> dict:
    if not qa_passed:
        return {
            "run_id": run_id,
            "write": write,
            "promoted_count": 0,
            "blocked": "qa_passed flag is required",
            "safety_warning": "approved-only external candidate review gate is not implemented yet",
        }
    if write:
        unlock = _promote_unlock_state()
        if not unlock["unlocked"]:
            return {
                "run_id": run_id,
                "write": False,
                "promoted_count": 0,
                "blocked": "legacy promote write requires EXTERNAL_PROMOTE_UNLOCK=true and approval file token",
                "unlock_state": unlock,
                "safety_warning": "legacy staging_places promote path is frozen by default",
            }
    conn = db_client.get_connection()
    try:
        rows = _load_staging(conn, run_id, region)
        if not write:
            role_counts: dict[str, int] = {}
            for row in rows:
                role_counts[row["visit_role"]] = role_counts.get(row["visit_role"], 0) + 1
            return {
                "run_id": run_id,
                "write": False,
                "candidate_count": len(rows),
                "role_counts": role_counts,
                "safety_warning": "dry-run only; production promote requires future approved-only review gate",
                "approved_only_promote_todo": APPROVED_ONLY_PROMOTE_TODO.strip(),
            }

        print(
            "[SAFETY WARNING] legacy --write unlocked by env+approval file before approved-only "
            "staging_external_places guard is implemented. Final preview is required.",
            file=sys.stderr,
        )
        promoted = 0
        snapshotted = 0
        try:
            for row in rows:
                snapshotted += _snapshot_existing(conn, run_id, row)
                promoted += _upsert_external(conn, row)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        log_step(conn, run_id, "promote_external_places", "SUCCESS", input_count=len(rows), output_count=promoted, metadata={"snapshot_count": snapshotted})
        finish_run(conn, run_id, "SUCCESS", {"external_promoted_count": promoted})
        return {
            "run_id": run_id,
            "write": True,
            "candidate_count": len(rows),
            "promoted_count": promoted,
            "snapshot_count": snapshotted,
            "safety_warning": "legacy staging_places promote path used; migrate to approved-only staging_external_places guard",
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote external staging_places into production places.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--region")
    parser.add_argument("--qa-passed", action="store_true", help="Required guard after QA confirms FAIL did not increase.")
    parser.add_argument("--write", action="store_true", help="Emergency legacy write path. Requires EXTERNAL_PROMOTE_UNLOCK=true and approval file token.")
    parser.add_argument("--approved-only-dry-run", action="store_true", help="Check staging_external_places approved-only preconditions without writing.")
    parser.add_argument("--approved-only-rehearsal", action="store_true", help="Simulate review and promote eligibility from clean_external_places without writing.")
    parser.add_argument("--shadow-mode", action="store_true", help="Compare legacy would-promote candidates with approved-only eligible candidates without writing.")
    parser.add_argument("--report", action="store_true", help="Write JSON/CSV/Markdown report for shadow mode.")
    parser.add_argument("--output-dir", default="qa_reports/shadow_mode", help="Report output directory.")
    parser.add_argument("--limit", type=int, default=100, help="Candidate cap for rehearsal mode.")
    parser.add_argument("--visit-role", choices=["cafe", "meal", "culture", "spot"], help="Optional slice filter for rehearsal/shadow mode.")
    parser.add_argument("--image-review-report", help="Optional image review gate JSON report for shadow-mode simulation only.")
    args = parser.parse_args()
    if args.shadow_mode:
        result = shadow_mode(args.run_id, args.region, args.limit, args.visit_role, args.image_review_report)
        if args.report:
            result["report_paths"] = write_shadow_report(result, args.output_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    if args.approved_only_rehearsal:
        print(json.dumps(approved_only_rehearsal(args.run_id, args.region, args.limit, args.visit_role), ensure_ascii=False, indent=2, default=str))
        return 0
    if args.approved_only_dry_run:
        print(json.dumps(approved_only_dry_run(args.run_id, args.region), ensure_ascii=False, indent=2, default=str))
        return 0
    print(json.dumps(promote(args.run_id, args.region, args.qa_passed, args.write), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
