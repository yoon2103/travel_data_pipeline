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


REVIEW_STATUSES = {
    "PENDING_REVIEW",
    "IN_REVIEW",
    "APPROVED",
    "REJECTED",
    "SKIPPED",
    "AUTO_APPROVED",
    "ROLLED_BACK",
}
ENRICHMENT_TYPES = {"IMAGE", "MOOD", "BUSINESS_STATUS", "DESCRIPTION", "PLACE_MATCH"}
SOURCE_TYPES = {"TOURAPI", "KAKAO", "NAVER", "MANUAL", "AI_GENERATED"}


def list_review_candidates(args: argparse.Namespace) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": args.limit}
    where: list[str] = []

    if args.review_status:
        where.append("review_status = %(review_status)s")
        params["review_status"] = args.review_status
    if args.enrichment_type:
        where.append("enrichment_type = %(enrichment_type)s")
        params["enrichment_type"] = args.enrichment_type
    if args.source_type:
        where.append("source_type = %(source_type)s")
        params["source_type"] = args.source_type
    if args.place_id is not None:
        where.append("place_id = %(place_id)s")
        params["place_id"] = args.place_id

    sql = """
        SELECT
            candidate_id,
            place_id,
            source_type,
            enrichment_type,
            review_status,
            promote_status,
            image_url,
            created_at
        FROM place_enrichment_candidates
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC, candidate_id DESC LIMIT %(limit)s"

    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List place enrichment candidates awaiting review.")
    parser.add_argument("--review-status", choices=sorted(REVIEW_STATUSES))
    parser.add_argument("--enrichment-type", choices=sorted(ENRICHMENT_TYPES))
    parser.add_argument("--source-type", choices=sorted(SOURCE_TYPES))
    parser.add_argument("--place-id", type=int)
    parser.add_argument("--limit", type=int, default=20)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.limit = min(max(args.limit, 1), 200)
    rows = list_review_candidates(args)
    print(json.dumps({"count": len(rows), "candidates": rows}, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
