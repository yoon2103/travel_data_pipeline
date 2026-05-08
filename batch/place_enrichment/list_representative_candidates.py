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


REVIEW_STATUSES = {"PENDING_REVIEW", "IN_REVIEW", "APPROVED", "REJECTED", "SKIPPED", "PROMOTED"}
PROMOTE_STATUSES = {"PENDING", "NOT_READY", "READY", "PROMOTED", "SKIPPED", "ROLLED_BACK"}
REPRESENTATIVE_STATUSES = {"CANDIDATE", "NEEDS_REVIEW", "APPROVED", "REJECTED", "PROMOTED"}
SOURCE_TYPES = {"TOURAPI", "KAKAO", "NAVER", "MANUAL"}


def list_candidates(args: argparse.Namespace) -> list[dict[str, Any]]:
    where: list[str] = []
    params: dict[str, Any] = {"limit": args.limit}

    if args.review_status:
        where.append("review_status = %(review_status)s")
        params["review_status"] = args.review_status
    if args.promote_status:
        where.append("promote_status = %(promote_status)s")
        params["promote_status"] = args.promote_status
    if args.representative_status:
        where.append("representative_status = %(representative_status)s")
        params["representative_status"] = args.representative_status
    if args.source_type:
        where.append("source_type = %(source_type)s")
        params["source_type"] = args.source_type
    if args.expected_name:
        where.append("expected_poi_name = %(expected_name)s")
        params["expected_name"] = args.expected_name

    sql = """
        SELECT
            candidate_id,
            expected_poi_name,
            source_type,
            source_name,
            confidence_score,
            representative_status,
            review_status,
            promote_status,
            COALESCE(validation_payload->'risk_flags', '[]'::jsonb) AS risk_flags,
            created_at
        FROM representative_poi_candidates
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY confidence_score DESC NULLS LAST, created_at DESC, candidate_id DESC LIMIT %(limit)s"

    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List representative POI candidates awaiting review.")
    parser.add_argument("--review-status", choices=sorted(REVIEW_STATUSES))
    parser.add_argument("--promote-status", choices=sorted(PROMOTE_STATUSES))
    parser.add_argument("--representative-status", choices=sorted(REPRESENTATIVE_STATUSES))
    parser.add_argument("--source-type", choices=sorted(SOURCE_TYPES))
    parser.add_argument("--expected-name")
    parser.add_argument("--limit", type=int, default=20)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.limit = min(max(args.limit, 1), 500)
    rows = list_candidates(args)
    print(json.dumps({"count": len(rows), "candidates": rows}, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
