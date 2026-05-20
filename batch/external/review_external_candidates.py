from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from batch.external.stage_external_candidates import build_candidates  # noqa: E402


REPORT_FIELDS = [
    "review_decision",
    "block_reasons",
    "name",
    "region",
    "source",
    "external_id",
    "visit_role",
    "category",
    "address",
    "image_available",
    "coordinate_valid",
    "duplicate_risk",
    "duplicate_of_place_id",
    "duplicate_match_name",
    "business_status",
    "business_safety_status",
    "proposed_action",
    "place_url",
]


def _write_csv(path: Path, candidates: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        for row in candidates:
            flat = {field: row.get(field) for field in REPORT_FIELDS}
            flat["block_reasons"] = "|".join(row.get("block_reasons") or [])
            writer.writerow(flat)


def _markdown_table(candidates: list[dict[str, Any]], max_rows: int = 80) -> str:
    lines = [
        "| decision | name | region | role | source | image | coord | duplicate | business | reasons |",
        "|---|---|---|---|---|---:|---:|---:|---|---|",
    ]
    for row in candidates[:max_rows]:
        reasons = ", ".join(row.get("block_reasons") or [])
        lines.append(
            "| {decision} | {name} | {region} | {role} | {source} | {image} | {coord} | {dup} | {business} | {reasons} |".format(
                decision=row.get("review_decision") or "",
                name=str(row.get("name") or "").replace("|", "/"),
                region=row.get("region") or "",
                role=row.get("visit_role") or "",
                source=row.get("source") or "",
                image="Y" if row.get("image_available") else "N",
                coord="Y" if row.get("coordinate_valid") else "N",
                dup="Y" if row.get("duplicate_risk") else "N",
                business=row.get("business_safety_status") or "",
                reasons=reasons.replace("|", "/"),
            )
        )
    return "\n".join(lines)


def _write_markdown(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = result["summary"]
    candidates = result["candidates"]
    content = f"""# External Candidate Review Report

## Summary

- run_id: `{summary.get("run_id")}`
- region: `{summary.get("region") or "ALL"}`
- candidate_count: {summary.get("candidate_count")}
- approve_candidate_count: {summary.get("approve_candidate_count")}
- review_required_count: {summary.get("review_required_count")}
- blocked_count: {summary.get("blocked_count")}
- duplicate_suspicious_count: {summary.get("duplicate_suspicious_count")}
- missing_image_count: {summary.get("missing_image_count")}
- missing_coordinate_count: {summary.get("missing_coordinate_count")}
- category_mismatch_count: {summary.get("category_mismatch_count")}
- business_closed_or_suspicious_count: {summary.get("business_closed_or_suspicious_count")}

## Decision Meaning

- `APPROVE_CANDIDATE`: QA/reviewer approval candidate. 실제 promote는 아직 금지.
- `REVIEW_REQUIRED`: duplicate, image, category 등 수동 확인 필요.
- `BLOCK_DUPLICATE_RISK`: 기존 places와 중복 가능성.
- `BLOCK_MISSING_COORDINATE`: 좌표 누락 또는 한국 좌표 범위 밖.
- `BLOCK_CATEGORY_RISK`: 숙박/병원/학교/행정시설 등 category risk.
- `BLOCK_MISSING_IMAGE`: 이미지 없음. 자동 차단은 아니지만 reviewer 확인 필요.

## Candidates

{_markdown_table(candidates)}
"""
    path.write_text(content, encoding="utf-8")


def _review_action_payload(args: argparse.Namespace) -> dict[str, Any] | None:
    action = "approve" if args.approve is not None else "reject" if args.reject is not None else None
    candidate_id = args.approve if args.approve is not None else args.reject
    if action is None:
        return None
    errors: list[str] = []
    if not args.reviewer:
        errors.append("--reviewer is required for approve/reject persistence")
    if not args.review_note:
        errors.append("--review-note is required for approve/reject persistence")
    return {
        "write": False,
        "action": action,
        "candidate_id": candidate_id,
        "reviewer": args.reviewer,
        "review_note": args.review_note,
        "target_table": "staging_external_places",
        "intended_update": {
            "promotion_status": "approved" if action == "approve" else "rejected",
            "reviewer": args.reviewer,
            "review_note": args.review_note,
            "reviewed_at": "NOW()",
        },
        "blocked": "review persistence is dry-run only until staging_external_places migration is applied",
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate dry-run review reports for external candidates.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--region")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--visit-role", choices=["cafe", "meal", "culture", "spot"], help="Optional slice filter for review reports.")
    parser.add_argument("--report", action="store_true", help="Write markdown and CSV reports.")
    parser.add_argument("--output-dir", default="qa_reports/external_candidate_review")
    parser.add_argument("--approve", type=int, help="Dry-run approve action for staging_external_places.id.")
    parser.add_argument("--reject", type=int, help="Dry-run reject action for staging_external_places.id.")
    parser.add_argument("--reviewer", help="Reviewer name or operator id. Required for approve/reject.")
    parser.add_argument("--review-note", help="Review note. Required for approve/reject.")
    args = parser.parse_args()

    if args.approve is not None and args.reject is not None:
        raise SystemExit("--approve and --reject cannot be used together")

    action_payload = _review_action_payload(args)
    if action_payload is not None:
        print(json.dumps(action_payload, ensure_ascii=False, indent=2))
        return 2 if action_payload["errors"] else 0

    result = build_candidates(args.run_id, args.region, args.limit, args.visit_role)
    output_dir = Path(args.output_dir)
    if args.report:
        stem = f"external_candidate_review_{args.run_id}"
        if args.region:
            stem += f"_{args.region}"
        csv_path = output_dir / f"{stem}.csv"
        md_path = output_dir / f"{stem}.md"
        json_path = output_dir / f"{stem}.json"
        _write_csv(csv_path, result["candidates"])
        _write_markdown(md_path, result)
        json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        result["report_paths"] = {
            "csv": str(csv_path),
            "markdown": str(md_path),
            "json": str(json_path),
        }
    print(json.dumps(result["summary"] | {"report_paths": result.get("report_paths", {})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
