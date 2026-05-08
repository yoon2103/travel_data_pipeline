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
from batch.place_enrichment.image_qa_policy import qa_checklist, qa_payload  # noqa: E402


REVIEW_STATUSES = {"PENDING_REVIEW", "IN_REVIEW", "APPROVED", "REJECTED", "SKIPPED", "PROMOTED"}
QUALITY_LEVELS = {"BLOCKED", "LOW", "REVIEW_REQUIRED", "GOOD", "REPRESENTATIVE_GRADE"}


def fetch_candidates(args: argparse.Namespace) -> list[dict[str, Any]]:
    where = ["source_type = 'MANUAL'", "category = 'REPRESENTATIVE_IMAGE'"]
    params: dict[str, Any] = {"limit": args.limit}
    if args.expected_name:
        where.append("expected_poi_name = %(expected_name)s")
        params["expected_name"] = args.expected_name
    if args.review_status:
        where.append("review_status = %(review_status)s")
        params["review_status"] = args.review_status

    sql = f"""
        SELECT
            candidate_id,
            expected_poi_name,
            source_type,
            source_name,
            category,
            image_url,
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
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC, candidate_id DESC
        LIMIT %(limit)s
    """
    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_duplicate_counts(image_urls: list[str]) -> dict[str, int]:
    urls = [url for url in image_urls if url]
    if not urls:
        return {}
    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT image_url, count(1) AS count
                FROM representative_poi_candidates
                WHERE image_url = ANY(%s)
                  AND image_url IS NOT NULL
                  AND trim(image_url) <> ''
                GROUP BY image_url
                """,
                (urls,),
            )
            return {row["image_url"]: int(row["count"]) for row in cur.fetchall()}
    finally:
        conn.close()


def to_summary(candidate: dict[str, Any], duplicate_count: int) -> dict[str, Any]:
    qa = qa_payload(candidate, duplicate_count=duplicate_count)
    return {
        "candidate_id": candidate["candidate_id"],
        "expected_poi_name": candidate["expected_poi_name"],
        "image_url": candidate["image_url"],
        "source_credit": qa.get("source_credit"),
        "quality_level": qa["quality_level"],
        "review_status": candidate["review_status"],
        "promote_status": candidate["promote_status"],
        "risk_flags": qa["risk_flags"],
        "qa_summary": qa,
    }


def list_image_candidates(args: argparse.Namespace) -> dict[str, Any]:
    args.limit = min(max(args.limit, 1), 500)
    rows = fetch_candidates(args)
    duplicate_counts = fetch_duplicate_counts([row.get("image_url") for row in rows])
    summaries = [
        to_summary(row, duplicate_counts.get(row.get("image_url"), 0))
        for row in rows
    ]
    if args.quality_level:
        summaries = [row for row in summaries if row["quality_level"] == args.quality_level]
    return {
        "mode": "read-only",
        "db_write": False,
        "places_changed": False,
        "seed_changed": False,
        "promote_executed": False,
        "count": len(summaries),
        "candidates": summaries,
        "qa_checklist": qa_checklist() if args.checklist else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List representative image candidates with QA summary.")
    parser.add_argument("--expected-name")
    parser.add_argument("--review-status", choices=sorted(REVIEW_STATUSES))
    parser.add_argument("--quality-level", choices=sorted(QUALITY_LEVELS))
    parser.add_argument("--checklist", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    return parser


def print_human(report: dict[str, Any]) -> None:
    print("[Representative Image QA Candidates]")
    print("- mode: read-only")
    print("- db_write: false")
    print("- places_changed: false")
    print("- seed_changed: false")
    print("- promote_executed: false")
    print(f"- count: {report['count']}")
    for row in report["candidates"]:
        print()
        print(f"## candidate_id={row['candidate_id']} / {row['expected_poi_name']}")
        print(f"- image_url: {row['image_url']}")
        print(f"- source_credit: {row['source_credit']}")
        print(f"- quality_level: {row['quality_level']}")
        print(f"- review_status: {row['review_status']}")
        print(f"- promote_status: {row['promote_status']}")
        print(f"- risk_flags: {row['risk_flags']}")
        print(f"- source_validity: {row['qa_summary']['source_validity']}")
        print(f"- license_validity: {row['qa_summary']['license_validity']}")
        print(f"- resolution: {row['qa_summary']['resolution']}")
    if report.get("qa_checklist"):
        print()
        print("[QA Checklist]")
        for item in report["qa_checklist"]:
            print(f"- {item['item']}: {item['pass']}")


def main() -> int:
    args = build_parser().parse_args()
    report = list_image_candidates(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, default=str, indent=2))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
