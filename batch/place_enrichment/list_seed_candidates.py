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


SEED_STATUSES = {
    "CANDIDATE",
    "NEEDS_REVIEW",
    "APPROVED",
    "REJECTED",
    "COEXIST",
    "READY_FOR_PROMOTE",
    "PROMOTED",
    "ROLLED_BACK",
}
REVIEW_STATUSES = {"PENDING_REVIEW", "IN_REVIEW", "APPROVED", "REJECTED", "SKIPPED"}
PROMOTE_STRATEGIES = {
    "KEEP_EXISTING_ONLY",
    "COEXIST_WITH_EXISTING",
    "REPLACE_EXISTING",
    "REPRESENTATIVE_ALIAS_ONLY",
}


def list_seed_candidates(args: argparse.Namespace) -> list[dict[str, Any]]:
    where = []
    params: dict[str, Any] = {"limit": args.limit}
    if args.expected_name:
        where.append("expected_poi_name = %(expected_name)s")
        params["expected_name"] = args.expected_name
    if args.region:
        where.append("region_1 = %(region)s")
        params["region"] = args.region
    if args.seed_status:
        where.append("seed_status = %(seed_status)s")
        params["seed_status"] = args.seed_status
    if args.review_status:
        where.append("review_status = %(review_status)s")
        params["review_status"] = args.review_status
    if args.strategy:
        where.append("promote_strategy = %(strategy)s")
        params["strategy"] = args.strategy

    sql = """
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
            dry_run_payload->>'readiness' AS readiness,
            created_at,
            updated_at
        FROM seed_candidates
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC, seed_candidate_id DESC LIMIT %(limit)s"

    conn = db_client.get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List seed candidates.")
    parser.add_argument("--expected-name")
    parser.add_argument("--region")
    parser.add_argument("--seed-status", choices=sorted(SEED_STATUSES))
    parser.add_argument("--review-status", choices=sorted(REVIEW_STATUSES))
    parser.add_argument("--strategy", choices=sorted(PROMOTE_STRATEGIES))
    parser.add_argument("--limit", type=int, default=20)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.limit = min(max(args.limit, 1), 500)
    rows = list_seed_candidates(args)
    print(json.dumps({"count": len(rows), "seed_candidates": rows}, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
