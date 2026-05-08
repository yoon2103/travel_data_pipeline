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
REVIEWABLE_STATUSES = {"PENDING_REVIEW", "IN_REVIEW"}


class RepresentativeReviewError(ValueError):
    pass


def fetch_candidate(conn, candidate_id: int) -> dict[str, Any] | None:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                candidate_id,
                expected_poi_name,
                source_type,
                source_name,
                confidence_score,
                representative_status,
                review_status,
                promote_status,
                review_payload
            FROM representative_poi_candidates
            WHERE candidate_id = %s
            """,
            (candidate_id,),
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


def review_candidate(args: argparse.Namespace) -> dict[str, Any]:
    reviewer = (args.reviewer or "").strip()
    if not reviewer:
        raise RepresentativeReviewError("reviewer is required")

    action = args.action
    target_status = ACTION_TO_STATUS[action]
    reviewed_at = datetime.now(timezone.utc).isoformat()
    note = (args.note or "").strip() or None

    conn = db_client.get_connection()
    try:
        candidate = fetch_candidate(conn, args.candidate_id)
        if not candidate:
            raise RepresentativeReviewError(f"candidate_id does not exist: {args.candidate_id}")

        previous_status = candidate["review_status"]
        if previous_status not in REVIEWABLE_STATUSES:
            return {
                "status": "ALREADY_REVIEWED",
                "dry_run": args.dry_run,
                "candidate_id": args.candidate_id,
                "previous_status": previous_status,
                "review_status": previous_status,
                "promote_status": candidate["promote_status"],
                "message": "Only PENDING_REVIEW or IN_REVIEW candidates can be reviewed.",
            }

        review_payload = build_review_payload(
            candidate.get("review_payload"),
            reviewer_id=reviewer,
            action=action,
            note=note,
            previous_status=previous_status,
            reviewed_at=reviewed_at,
        )

        if args.dry_run:
            return {
                "status": "DRY_RUN",
                "dry_run": True,
                "candidate_id": args.candidate_id,
                "previous_status": previous_status,
                "review_status": target_status,
                "promote_status": candidate["promote_status"],
                "review_payload": review_payload,
            }

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE representative_poi_candidates
                SET review_status = %s,
                    review_payload = %s,
                    updated_at = NOW()
                WHERE candidate_id = %s
                  AND review_status IN ('PENDING_REVIEW', 'IN_REVIEW')
                RETURNING candidate_id, review_status, promote_status, review_payload
                """,
                (
                    target_status,
                    psycopg2.extras.Json(review_payload),
                    args.candidate_id,
                ),
            )
            updated = cur.fetchone()
        if not updated:
            conn.rollback()
            raise RepresentativeReviewError(f"candidate_id could not be reviewed: {args.candidate_id}")
        conn.commit()
        return {
            "status": "UPDATED",
            "dry_run": False,
            "candidate_id": int(updated[0]),
            "previous_status": previous_status,
            "review_status": updated[1],
            "promote_status": updated[2],
            "review_payload": updated[3],
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Approve, reject, or skip a representative POI candidate.")
    parser.add_argument("--candidate-id", type=int, required=True)
    parser.add_argument("--action", choices=sorted(ACTION_TO_STATUS), required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--note")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = review_candidate(args)
    except RepresentativeReviewError as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
