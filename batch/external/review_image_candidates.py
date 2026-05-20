from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DECISIONS = {
    "IMAGE_REVIEW_REQUIRED",
    "IMAGE_APPROVED_SIMULATED",
    "IMAGE_REJECTED_SIMULATED",
    "IMAGE_BLOCKED_MISMATCH",
    "IMAGE_BLOCKED_LICENSE_RISK",
    "IMAGE_LOW_CONFIDENCE_REVIEW",
}

CSV_FIELDS = [
    "place_name",
    "confidence",
    "score",
    "image_thumbnail",
    "source_page",
    "mismatch_reason",
    "license_source_risk",
    "recommended_action",
    "simulated_reviewer_decision",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def persistence_action_payload(args: argparse.Namespace) -> dict[str, Any] | None:
    action = None
    target = None
    if args.approve_image:
        action = "approve_image"
        target = args.approve_image
    if args.reject_image:
        if action:
            return {
                "write": False,
                "blocked": True,
                "reason": "approve_image and reject_image are mutually exclusive",
            }
        action = "reject_image"
        target = args.reject_image
    if not action and not args.write:
        return None

    missing: list[str] = []
    if action and not args.reviewer:
        missing.append("--reviewer")
    if action and not args.review_note:
        missing.append("--review-note")

    return {
        "write": False,
        "blocked": True,
        "action": action or "write_requested_without_review_action",
        "target": target,
        "reviewer": args.reviewer,
        "review_note": args.review_note,
        "missing_required_args": missing,
        "target_table_options": [
            "staging_external_places image review columns",
        ],
        "reason": (
            "Image review persistence is intentionally blocked until the "
            "staging_external_places image review columns migration is applied."
        ),
    }


def find_review_row(rows: list[dict[str, Any]], target: str | None) -> dict[str, Any] | None:
    if not target:
        return None
    normalized = target.strip().lower()
    for row in rows:
        if str(row.get("place_name") or "").strip().lower() == normalized:
            return row
    return None


def persistence_status_for_action(action: str, row: dict[str, Any] | None) -> tuple[str, str | None]:
    if action == "approve_image":
        return "approved", None
    if row and row.get("license_source_risk") == "HIGH_PINTEREST_OR_PINIMG":
        return "blocked_license", "license_source_risk"
    if row and row.get("confidence") == "LOW":
        return "low_confidence", "low_confidence"
    return "rejected", "reviewer_rejected"


def build_persistence_rehearsal(args: argparse.Namespace, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not args.persistence_rehearsal and not args.simulate_write:
        return None

    action = None
    target = None
    if args.approve_image:
        action = "approve_image"
        target = args.approve_image
    if args.reject_image:
        if action:
            return {
                "write_mode": "SIMULATION_ONLY",
                "blocked": True,
                "reason": "approve_image and reject_image are mutually exclusive",
            }
        action = "reject_image"
        target = args.reject_image

    row = find_review_row(rows, target)
    missing: list[str] = []
    if not action:
        missing.append("--approve-image or --reject-image")
    if not args.reviewer:
        missing.append("--reviewer")
    if not args.review_note:
        missing.append("--review-note")
    if action == "approve_image" and not args.image_license_note:
        missing.append("--image-license-note")

    status, block_reason = persistence_status_for_action(action or "none", row)
    image_url = row.get("image_link") if row else None
    image_thumb_url = row.get("image_thumbnail") if row else None
    image_reviewed_at = utc_now_iso()
    staging_payload = {
        "staging_external_place_id": args.staging_external_place_id,
        "image_review_status": status if not missing and row else "needs_manual_review",
        "image_source": "naver_image_search",
        "image_url": image_url,
        "image_thumb_url": image_thumb_url,
        "image_confidence": row.get("confidence") if row else None,
        "image_license_note": args.image_license_note,
        "image_reviewer": args.reviewer,
        "image_review_note": args.review_note,
        "image_reviewed_at": image_reviewed_at,
        "image_block_reason": block_reason,
    }
    rehearsal = {
        "write_mode": "SIMULATION_ONLY",
        "db_write": False,
        "migration_required_before_write": True,
        "blocked_from_real_write": True,
        "action": action,
        "candidate": target,
        "candidate_found": row is not None,
        "missing_required_args": missing,
        "staging_external_places_update_payload": staging_payload,
        "promote_validator_effect": {
            "block_missing_image_cleared": bool(
                action == "approve_image"
                and row
                and image_url
                and args.image_license_note
                and not missing
            ),
            "policy": "BLOCK_MISSING_IMAGE can clear only after image_review_status='approved' plus image_url and image_license_note.",
        },
    }
    return rehearsal


def safe_filename(value: str | None) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣_-]+", "_", str(value or "all")).strip("_") or "all"


def load_poc_report(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def license_risk(row: dict[str, Any]) -> str:
    thumbnail = str(row.get("best_thumbnail") or "").lower()
    candidates = row.get("candidates") or []
    first = candidates[0] if candidates else {}
    image_link = str(first.get("image_link") or "").lower()
    source_page = str(first.get("source_page") or "").lower()
    text = " ".join([thumbnail, image_link, source_page])
    if "pinimg" in text or "pinterest" in text:
        return "HIGH_PINTEREST_OR_PINIMG"
    if "blog" in text:
        return "MEDIUM_BLOG_SOURCE"
    if "ldb-phinf.pstatic.net" in text:
        return "LOW_NAVER_PLACE_CDN"
    if "pstatic.net" in text:
        return "MEDIUM_NAVER_SEARCH_PROXY"
    if not thumbnail:
        return "HIGH_NO_THUMBNAIL"
    return "MEDIUM_UNKNOWN_SOURCE"


def decide(row: dict[str, Any], simulate_approve_high: bool) -> str:
    confidence = row.get("best_confidence")
    mismatch = row.get("best_mismatch_risk")
    risk = license_risk(row)
    if mismatch and mismatch != "none":
        if "pinimg" in mismatch or "pinterest" in mismatch or risk.startswith("HIGH"):
            return "IMAGE_BLOCKED_LICENSE_RISK"
        return "IMAGE_BLOCKED_MISMATCH"
    if confidence == "HIGH":
        return "IMAGE_APPROVED_SIMULATED" if simulate_approve_high else "IMAGE_REVIEW_REQUIRED"
    if confidence == "MEDIUM":
        return "IMAGE_REVIEW_REQUIRED"
    if confidence == "LOW":
        return "IMAGE_LOW_CONFIDENCE_REVIEW"
    return "IMAGE_REJECTED_SIMULATED"


def image_review_status_for_decision(decision: str) -> str:
    if decision == "IMAGE_APPROVED_SIMULATED":
        return "approved"
    if decision == "IMAGE_BLOCKED_LICENSE_RISK":
        return "blocked_license"
    if decision == "IMAGE_LOW_CONFIDENCE_REVIEW":
        return "low_confidence"
    if decision == "IMAGE_BLOCKED_MISMATCH":
        return "rejected"
    return "needs_manual_review"


def review_rows(
    poc: dict[str, Any],
    simulate_approve_high: bool,
    limit: int | None,
    image_license_note: str | None = None,
) -> list[dict[str, Any]]:
    rows = poc.get("results") or []
    if limit:
        rows = rows[:limit]
    reviewed: list[dict[str, Any]] = []
    for row in rows:
        candidates = row.get("candidates") or []
        first = candidates[0] if candidates else {}
        decision = decide(row, simulate_approve_high)
        review_status = image_review_status_for_decision(decision)
        reviewed.append(
            {
                "place_name": row.get("place_name"),
                "region": row.get("region"),
                "category": row.get("category"),
                "query": row.get("query"),
                "confidence": row.get("best_confidence"),
                "score": row.get("best_score"),
                "image_thumbnail": row.get("best_thumbnail"),
                "image_link": first.get("image_link"),
                "source_page": first.get("source_page"),
                "mismatch_reason": row.get("best_mismatch_risk"),
                "license_source_risk": license_risk(row),
                "recommended_action": row.get("recommended_action"),
                "simulated_reviewer_decision": decision,
                "image_approved_simulated": decision == "IMAGE_APPROVED_SIMULATED",
                "image_review_status": review_status,
                "image_license_note": image_license_note if review_status == "approved" else None,
            }
        )
    return reviewed


def summarize(poc: dict[str, Any], rows: list[dict[str, Any]], simulate_approve_high: bool) -> dict[str, Any]:
    decisions: dict[str, int] = {}
    for row in rows:
        decision = row["simulated_reviewer_decision"]
        decisions[decision] = decisions.get(decision, 0) + 1
    return {
        "run_id": poc.get("summary", {}).get("run_id"),
        "region": poc.get("summary", {}).get("region"),
        "visit_role": poc.get("summary", {}).get("visit_role"),
        "write": False,
        "simulate_approve_high": simulate_approve_high,
        "candidate_count": len(rows),
        "image_approved_simulated_count": decisions.get("IMAGE_APPROVED_SIMULATED", 0),
        "image_review_required_count": decisions.get("IMAGE_REVIEW_REQUIRED", 0),
        "image_low_confidence_review_count": decisions.get("IMAGE_LOW_CONFIDENCE_REVIEW", 0),
        "image_blocked_mismatch_count": decisions.get("IMAGE_BLOCKED_MISMATCH", 0),
        "image_blocked_license_risk_count": decisions.get("IMAGE_BLOCKED_LICENSE_RISK", 0),
        "image_rejected_simulated_count": decisions.get("IMAGE_REJECTED_SIMULATED", 0),
        "decision_counts": dict(sorted(decisions.items())),
        "scraping_used": False,
        "production_places_write": False,
        "migration_executed": False,
    }


def write_reports(result: dict[str, Any], output_dir: str) -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = result["summary"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stem = "image_review_gate_{run_id}_{region}_{role}_{timestamp}".format(
        run_id=safe_filename(summary.get("run_id")),
        region=safe_filename(summary.get("region")),
        role=safe_filename(summary.get("visit_role")),
        timestamp=timestamp,
    )
    json_path = out / f"{stem}.json"
    csv_path = out / f"{stem}.csv"
    md_path = out / f"{stem}.md"

    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in result["review_rows"]:
            writer.writerow({field: row.get(field) for field in CSV_FIELDS})

    lines = [
        "# Image Review Gate Simulation",
        "",
        "## Summary",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Review Rows",
            "",
            "| place | confidence | score | thumbnail | source page | mismatch | license risk | decision |",
            "|---|---|---:|---|---|---|---|---|",
        ]
    )
    for row in result["review_rows"]:
        thumbnail = row.get("image_thumbnail") or ""
        source_page = row.get("source_page") or ""
        lines.append(
            "| {place} | {confidence} | {score} | {thumb} | {source} | {mismatch} | {risk} | {decision} |".format(
                place=str(row.get("place_name") or "").replace("|", "/"),
                confidence=row.get("confidence"),
                score=row.get("score"),
                thumb=f"[preview]({thumbnail})" if thumbnail else "",
                source=f"[source]({source_page})" if source_page else "",
                mismatch=str(row.get("mismatch_reason") or "").replace("|", "/"),
                risk=row.get("license_source_risk"),
                decision=row.get("simulated_reviewer_decision"),
            )
        )
    lines.extend(
        [
            "",
            "## Decision Taxonomy",
            "",
            "- `IMAGE_REVIEW_REQUIRED`: reviewer must inspect the image before approval.",
            "- `IMAGE_APPROVED_SIMULATED`: HIGH confidence image approved only in simulation mode.",
            "- `IMAGE_REJECTED_SIMULATED`: no usable image candidate in simulation.",
            "- `IMAGE_BLOCKED_MISMATCH`: image/title/source mismatch risk.",
            "- `IMAGE_BLOCKED_LICENSE_RISK`: source/license risk such as Pinterest or unknown unsafe source.",
            "- `IMAGE_LOW_CONFIDENCE_REVIEW`: low confidence image candidate; reject or manual review.",
            "",
            "No DB write, no migration, no scraping, no automatic production approval.",
        ]
    )
    if result.get("persistence_rehearsal"):
        rehearsal = result["persistence_rehearsal"]
        lines.extend(
            [
                "",
                "## Persistence Rehearsal",
                "",
                f"- write_mode: `{rehearsal.get('write_mode')}`",
                f"- db_write: `{rehearsal.get('db_write')}`",
                f"- action: `{rehearsal.get('action')}`",
                f"- candidate: `{rehearsal.get('candidate')}`",
                f"- candidate_found: `{rehearsal.get('candidate_found')}`",
                f"- image_review_status: `{rehearsal.get('staging_external_places_update_payload', {}).get('image_review_status')}`",
                f"- image_confidence: `{rehearsal.get('staging_external_places_update_payload', {}).get('image_confidence')}`",
                f"- image_license_note: `{rehearsal.get('staging_external_places_update_payload', {}).get('image_license_note')}`",
                f"- block_missing_image_cleared: `{rehearsal.get('promote_validator_effect', {}).get('block_missing_image_cleared')}`",
                "",
                "Planned update is simulation-only. Migration must be applied before any real persistence write.",
            ]
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Report-only image review gate simulation.")
    parser.add_argument("--run-id")
    parser.add_argument("--region")
    parser.add_argument("--visit-role")
    parser.add_argument("--input-report", required=True)
    parser.add_argument("--output-dir", default="qa_reports/image_review_gate")
    parser.add_argument("--simulate-approve-high", action="store_true")
    parser.add_argument("--approve-image", help="Draft persistence action target; write is blocked until migration is applied.")
    parser.add_argument("--reject-image", help="Draft persistence action target; write is blocked until migration is applied.")
    parser.add_argument("--reviewer", help="Reviewer name for future persistence workflow.")
    parser.add_argument("--review-note", help="Reviewer note for future persistence workflow.")
    parser.add_argument("--image-license-note", help="Required for approve rehearsal; records source/license basis.")
    parser.add_argument("--staging-external-place-id", type=int, help="Optional staging_external_places.id for rehearsal payload.")
    parser.add_argument("--persistence-rehearsal", action="store_true", help="Generate planned image review persistence payload without writing.")
    parser.add_argument("--simulate-write", action="store_true", help="Alias-style rehearsal flag; still performs no DB write.")
    parser.add_argument("--write", action="store_true", help="Blocked placeholder; no DB write before migration.")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    persistence_action = persistence_action_payload(args)
    poc = load_poc_report(args.input_report)
    rows = review_rows(poc, args.simulate_approve_high, args.limit, args.image_license_note)
    summary = summarize(poc, rows, args.simulate_approve_high)
    if args.run_id:
        summary["run_id"] = args.run_id
    if args.region:
        summary["region"] = args.region
    if args.visit_role:
        summary["visit_role"] = args.visit_role
    if persistence_action:
        summary["persistence_action"] = persistence_action
    result = {"summary": summary, "review_rows": rows}
    persistence_rehearsal = build_persistence_rehearsal(args, rows)
    if persistence_rehearsal:
        result["persistence_rehearsal"] = persistence_rehearsal
        summary["persistence_rehearsal"] = {
            "write_mode": persistence_rehearsal.get("write_mode"),
            "action": persistence_rehearsal.get("action"),
            "candidate": persistence_rehearsal.get("candidate"),
            "candidate_found": persistence_rehearsal.get("candidate_found"),
            "image_review_status": persistence_rehearsal.get("staging_external_places_update_payload", {}).get("image_review_status"),
            "block_missing_image_cleared": persistence_rehearsal.get("promote_validator_effect", {}).get("block_missing_image_cleared"),
        }
    result["report_paths"] = write_reports(result, args.output_dir)
    print(json.dumps(summary | {"report_paths": result["report_paths"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
