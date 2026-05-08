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
from batch.place_enrichment.image_qa_policy import qa_checklist, qa_payload  # noqa: E402


QUALITY_ORDER = {
    "BLOCKED": 0,
    "LOW": 1,
    "REVIEW_REQUIRED": 2,
    "GOOD": 3,
    "REPRESENTATIVE_GRADE": 4,
}
APPROVABLE_LEVELS = {"GOOD", "REPRESENTATIVE_GRADE"}
ACTION_TO_STATUS = {
    "approve": "APPROVED",
    "reject": "REJECTED",
}
REVIEWABLE_STATUSES = {"PENDING_REVIEW", "IN_REVIEW"}


class RepresentativeImageReviewError(ValueError):
    def __init__(self, message: str, *, code: str = "VALIDATION_ERROR", details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def fetch_candidate(conn, candidate_id: int) -> dict[str, Any] | None:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                candidate_id,
                expected_poi_name,
                source_type,
                source_name,
                category,
                image_url,
                review_status,
                promote_status,
                source_payload,
                validation_payload,
                review_payload,
                created_at,
                updated_at
            FROM representative_poi_candidates
            WHERE candidate_id = %s
            """,
            (candidate_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def duplicate_count(conn, image_url: str | None) -> int:
    if not image_url:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(1) AS count
            FROM representative_poi_candidates
            WHERE image_url = %s
              AND image_url IS NOT NULL
              AND trim(image_url) <> ''
            """,
            (image_url,),
        )
        row = cur.fetchone()
        return int(row["count"] if isinstance(row, dict) else row[0])


def validate_candidate(candidate: dict[str, Any]) -> None:
    if candidate.get("source_type") != "MANUAL" or candidate.get("category") != "REPRESENTATIVE_IMAGE":
        raise RepresentativeImageReviewError(
            "candidate is not a representative manual image candidate",
            code="NOT_REPRESENTATIVE_IMAGE",
            details={
                "source_type": candidate.get("source_type"),
                "category": candidate.get("category"),
            },
        )


def contamination_flags(args: argparse.Namespace) -> list[str]:
    flags = []
    for attr, name in [
        ("wrong_place_risk", "WRONG_PLACE_RISK"),
        ("nearby_business_risk", "NEARBY_BUSINESS_RISK"),
        ("watermark_detected", "WATERMARK_DETECTED"),
        ("advertisement_detected", "ADVERTISEMENT_DETECTED"),
        ("blurry", "BLURRY_IMAGE"),
        ("unrelated_image", "UNRELATED_IMAGE"),
    ]:
        if getattr(args, attr, False):
            flags.append(name)
    return flags


def validate_action(args: argparse.Namespace, qa: dict[str, Any], flags: list[str]) -> None:
    note = (args.note or "").strip()
    if not note:
        raise RepresentativeImageReviewError("review note is required", code="REVIEW_NOTE_REQUIRED")

    if args.action == "reject":
        return

    requested_level = args.quality_level
    if requested_level not in APPROVABLE_LEVELS:
        raise RepresentativeImageReviewError(
            "approve requires quality_level GOOD or REPRESENTATIVE_GRADE",
            code="QUALITY_LEVEL_NOT_APPROVABLE",
            details={"quality_level": requested_level},
        )
    if QUALITY_ORDER[requested_level] < QUALITY_ORDER.get(qa.get("quality_level"), 0):
        raise RepresentativeImageReviewError(
            "reviewer quality_level cannot be lower than automated QA level for approve",
            code="QUALITY_LEVEL_DOWNGRADE_ON_APPROVE",
            details={"qa_quality_level": qa.get("quality_level"), "reviewer_quality_level": requested_level},
        )
    if not args.landmark_identifiable:
        raise RepresentativeImageReviewError(
            "approve requires --landmark-identifiable",
            code="LANDMARK_IDENTIFIABLE_REQUIRED",
        )
    if flags:
        raise RepresentativeImageReviewError(
            "approve is blocked by contamination flags",
            code="CONTAMINATION_FLAGS_PRESENT",
            details={"contamination_flags": flags},
        )
    if qa.get("placeholder_domain"):
        raise RepresentativeImageReviewError("approve blocked: placeholder domain", code="PLACEHOLDER_IMAGE_URL")
    if qa.get("source_validity") != "VALID" or qa.get("license_validity") != "VALID":
        raise RepresentativeImageReviewError(
            "approve requires valid source and license",
            code="SOURCE_OR_LICENSE_INVALID",
            details={"source_validity": qa.get("source_validity"), "license_validity": qa.get("license_validity")},
        )


def build_review_payload(
    existing_payload: dict[str, Any] | None,
    *,
    args: argparse.Namespace,
    previous_status: str,
    qa: dict[str, Any],
    flags: list[str],
    reviewed_at: str,
) -> dict[str, Any]:
    payload = dict(existing_payload or {})
    visual_review_passed = args.action == "approve"
    final_quality_level = args.quality_level
    entry = {
        "reviewer_id": args.reviewer,
        "reviewed_at": reviewed_at,
        "review_action": args.action,
        "review_note": args.note,
        "previous_status": previous_status,
        "visual_review_passed": visual_review_passed,
        "reviewer_quality_grade": args.quality_level,
        "landmark_identifiable": bool(args.landmark_identifiable),
        "contamination_flags": flags,
        "final_quality_level": final_quality_level,
        "qa_summary": qa,
    }
    history = list(payload.get("visual_review_history") or [])
    history.append(entry)
    payload.update(entry)
    payload["visual_review_history"] = history
    payload["review_required"] = False if visual_review_passed else True
    return payload


def readiness_impact(candidate: dict[str, Any], action: str, qa: dict[str, Any]) -> dict[str, Any]:
    if action != "approve":
        return {
            "image_gap_resolved": False,
            "representative_readiness_impact": "IMAGE_MISSING remains",
            "next_readiness": "READY_WITH_IMAGE_GAP",
        }
    return {
        "image_gap_resolved": True,
        "representative_readiness_impact": "Approved representative image can satisfy IMAGE_MISSING for later dry-run.",
        "next_readiness": "READY_FOR_SEED_OVERLAY_QA_RECHECK",
        "quality_level": qa.get("quality_level"),
    }


def review_image_candidate(args: argparse.Namespace) -> dict[str, Any]:
    if not (args.reviewer or "").strip():
        raise RepresentativeImageReviewError("reviewer is required", code="REVIEWER_REQUIRED")
    conn = db_client.get_connection()
    try:
        candidate = fetch_candidate(conn, args.candidate_id)
        if not candidate:
            raise RepresentativeImageReviewError(
                f"candidate_id does not exist: {args.candidate_id}",
                code="CANDIDATE_NOT_FOUND",
            )
        validate_candidate(candidate)
        dup_count = duplicate_count(conn, candidate.get("image_url"))
        qa = qa_payload(candidate, duplicate_count=dup_count)
        flags = contamination_flags(args)
        validate_action(args, qa, flags)

        previous_status = candidate["review_status"]
        if previous_status not in REVIEWABLE_STATUSES:
            return {
                "status": "ALREADY_REVIEWED",
                "dry_run": args.dry_run,
                "candidate_id": args.candidate_id,
                "previous_status": previous_status,
                "review_status": previous_status,
                "promote_status": candidate["promote_status"],
                "pre_review": pre_review_payload(candidate, qa),
            }

        target_status = ACTION_TO_STATUS[args.action]
        reviewed_at = datetime.now(timezone.utc).isoformat()
        review_payload = build_review_payload(
            candidate.get("review_payload"),
            args=args,
            previous_status=previous_status,
            qa=qa,
            flags=flags,
            reviewed_at=reviewed_at,
        )
        result = {
            "status": "DRY_RUN" if args.dry_run else "UPDATED",
            "dry_run": args.dry_run,
            "candidate_id": args.candidate_id,
            "previous_status": previous_status,
            "review_status": target_status,
            "promote_status": candidate["promote_status"],
            "pre_review": pre_review_payload(candidate, qa),
            "review_payload": review_payload,
            "readiness_impact": readiness_impact(candidate, args.action, qa),
            "places_changed": False,
            "seed_changed": False,
            "promote_executed": False,
        }
        if args.dry_run:
            conn.rollback()
            return result

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE representative_poi_candidates
                SET review_status = %s,
                    review_payload = %s,
                    updated_at = NOW()
                WHERE candidate_id = %s
                  AND review_status IN ('PENDING_REVIEW', 'IN_REVIEW')
                RETURNING candidate_id
                """,
                (target_status, psycopg2.extras.Json(review_payload), args.candidate_id),
            )
            row = cur.fetchone()
            if not row:
                conn.rollback()
                raise RepresentativeImageReviewError(
                    f"candidate_id could not be reviewed: {args.candidate_id}",
                    code="REVIEW_UPDATE_FAILED",
                )
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def pre_review_payload(candidate: dict[str, Any], qa: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate["candidate_id"],
        "expected_poi_name": candidate["expected_poi_name"],
        "image_url": candidate["image_url"],
        "source_credit": qa.get("source_credit"),
        "image_source_url": qa.get("image_source_url"),
        "quality_level": qa.get("quality_level"),
        "metadata": qa.get("resolution"),
        "risk_flags": qa.get("risk_flags"),
        "duplicate_url_count": qa.get("duplicate_url_count"),
        "source_validity": qa.get("source_validity"),
        "license_validity": qa.get("license_validity"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Visual-review a representative image candidate.")
    parser.add_argument("--candidate-id", type=int, required=True)
    parser.add_argument("--action", choices=sorted(ACTION_TO_STATUS), required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--note", required=True)
    parser.add_argument("--quality-level", choices=sorted(QUALITY_ORDER), required=True)
    parser.add_argument("--landmark-identifiable", action="store_true")
    parser.add_argument("--wrong-place-risk", action="store_true")
    parser.add_argument("--nearby-business-risk", action="store_true")
    parser.add_argument("--watermark-detected", action="store_true")
    parser.add_argument("--advertisement-detected", action="store_true")
    parser.add_argument("--blurry", action="store_true")
    parser.add_argument("--unrelated-image", action="store_true")
    parser.add_argument("--checklist", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = review_image_candidate(args)
    except RepresentativeImageReviewError as exc:
        print(
            json.dumps(
                {"status": "ERROR", "error_code": exc.code, "reason": str(exc), "details": exc.details},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    if args.checklist:
        result["visual_qa_checklist"] = qa_checklist()
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
