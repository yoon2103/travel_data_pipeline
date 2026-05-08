from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config  # noqa: E402,F401
import db_client  # noqa: E402


ACTION_TO_STATUS = {
    "approve": "APPROVED",
    "reject": "REJECTED",
    "skip": "SKIPPED",
}
ACTION_TO_SEED_STATUS = {
    "approve": "APPROVED",
    "reject": "REJECTED",
    "skip": "NEEDS_REVIEW",
}
REVIEWABLE_STATUSES = {"PENDING_REVIEW", "IN_REVIEW"}


class SeedReviewError(ValueError):
    pass


def fetch_candidate(conn, seed_candidate_id: int) -> dict[str, Any] | None:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                seed_candidate_id,
                expected_poi_name,
                candidate_place_name,
                promote_strategy,
                seed_status,
                review_status,
                risk_flags,
                review_payload
            FROM seed_candidates
            WHERE seed_candidate_id = %s
            """,
            (seed_candidate_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def build_review_payload(
    existing_payload: dict[str, Any] | None,
    *,
    reviewer_id: str,
    action: str,
    note: str | None,
    previous_status: str,
    reviewed_at: str,
) -> dict[str, Any]:
    payload = dict(existing_payload or {})
    entry = {
        "reviewer_id": reviewer_id,
        "reviewed_at": reviewed_at,
        "review_action": action,
        "review_note": note,
        "previous_status": previous_status,
    }
    history = list(payload.get("review_history") or [])
    history.append(entry)
    payload.update(entry)
    payload["review_history"] = history
    return payload


def review_seed_candidate(args: argparse.Namespace) -> dict[str, Any]:
    reviewer = (args.reviewer or "").strip()
    if not reviewer:
        raise SeedReviewError("reviewer is required")

    conn = db_client.get_connection()
    try:
        candidate = fetch_candidate(conn, args.seed_candidate_id)
        if not candidate:
            raise SeedReviewError(f"seed_candidate_id does not exist: {args.seed_candidate_id}")

        previous_status = candidate["review_status"]
        if previous_status not in REVIEWABLE_STATUSES:
            return {
                "status": "ALREADY_REVIEWED",
                "dry_run": args.dry_run,
                "seed_candidate_id": args.seed_candidate_id,
                "previous_status": previous_status,
                "review_status": previous_status,
                "seed_status": candidate["seed_status"],
                "message": "Only PENDING_REVIEW or IN_REVIEW seed candidates can be reviewed.",
            }

        reviewed_at = datetime.now(timezone.utc).isoformat()
        target_review_status = ACTION_TO_STATUS[args.action]
        target_seed_status = ACTION_TO_SEED_STATUS[args.action]
        note = (args.note or "").strip() or None
        review_payload = build_review_payload(
            candidate.get("review_payload"),
            reviewer_id=reviewer,
            action=args.action,
            note=note,
            previous_status=previous_status,
            reviewed_at=reviewed_at,
        )

        if args.dry_run:
            return {
                "status": "DRY_RUN",
                "dry_run": True,
                "seed_candidate_id": args.seed_candidate_id,
                "previous_status": previous_status,
                "review_status": target_review_status,
                "seed_status": target_seed_status,
                "review_payload": review_payload,
            }

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE seed_candidates
                SET review_status = %s,
                    seed_status = %s,
                    review_payload = %s,
                    updated_at = NOW()
                WHERE seed_candidate_id = %s
                  AND review_status IN ('PENDING_REVIEW', 'IN_REVIEW')
                RETURNING seed_candidate_id, review_status, seed_status, review_payload
                """,
                (
                    target_review_status,
                    target_seed_status,
                    psycopg2.extras.Json(review_payload),
                    args.seed_candidate_id,
                ),
            )
            row = cur.fetchone()
        if not row:
            conn.rollback()
            raise SeedReviewError(f"seed_candidate_id could not be reviewed: {args.seed_candidate_id}")
        conn.commit()
        return {
            "status": "UPDATED",
            "dry_run": False,
            "seed_candidate_id": int(row[0]),
            "previous_status": previous_status,
            "review_status": row[1],
            "seed_status": row[2],
            "review_payload": row[3],
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Approve, reject, or skip a seed candidate.")
    parser.add_argument("--seed-candidate-id", type=int, required=True)
    parser.add_argument("--action", choices=sorted(ACTION_TO_STATUS), required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--note")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = review_seed_candidate(args)
    except SeedReviewError as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
