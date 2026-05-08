from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config  # noqa: E402,F401
import db_client  # noqa: E402


VALID_INTENDED_ROLES = {"primary", "gallery"}
VALID_INDOOR_OUTDOOR = {"indoor", "outdoor", "mixed"}


class ManualImageCandidateError(ValueError):
    pass


def validate_url(value: str | None, *, field_name: str, required: bool = False) -> str | None:
    value = (value or "").strip()
    if not value:
        if required:
            raise ManualImageCandidateError(f"{field_name} is required")
        return None

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ManualImageCandidateError(f"{field_name} must be an absolute http(s) URL")
    return value


def validate_inputs(args: argparse.Namespace) -> dict[str, Any]:
    image_url = validate_url(args.image_url, field_name="image_url", required=True)
    thumbnail_url = validate_url(args.thumbnail_url, field_name="thumbnail_url")
    image_source_url = validate_url(args.image_source_url, field_name="image_source_url")

    intended_role = (args.intended_role or "primary").strip().lower()
    if intended_role not in VALID_INTENDED_ROLES:
        raise ManualImageCandidateError(f"intended_role must be one of {sorted(VALID_INTENDED_ROLES)}")

    indoor_outdoor_hint = (args.indoor_outdoor_hint or "").strip().lower() or None
    if indoor_outdoor_hint and indoor_outdoor_hint not in VALID_INDOOR_OUTDOOR:
        raise ManualImageCandidateError(f"indoor_outdoor_hint must be one of {sorted(VALID_INDOOR_OUTDOOR)}")

    return {
        "place_id": args.place_id,
        "image_url": image_url,
        "thumbnail_url": thumbnail_url,
        "image_source_url": image_source_url,
        "source_credit": (args.source_credit or "").strip() or None,
        "license_note": (args.license_note or "").strip() or None,
        "curator_note": (args.curator_note or "").strip() or None,
        "intended_role": intended_role,
        "category_hint": (args.category_hint or "").strip() or None,
        "indoor_outdoor_hint": indoor_outdoor_hint,
    }


def source_place_id_for(image_url: str) -> str:
    digest = hashlib.sha256(image_url.encode("utf-8")).hexdigest()
    return f"manual-image:{digest[:32]}"


def fetch_place(conn, place_id: int) -> dict[str, Any] | None:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT place_id, name, category_id, region_1, region_2, visit_role,
                   indoor_outdoor, first_image_url, first_image_thumb_url
            FROM places
            WHERE place_id = %s
            """,
            (place_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def find_duplicate(conn, image_url: str) -> dict[str, Any] | None:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT candidate_id, place_id, source_type, review_status, promote_status
            FROM place_enrichment_candidates
            WHERE enrichment_type = 'IMAGE'
              AND image_url = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (image_url,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def build_payloads(place: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    source_payload = {
        "source_type": "MANUAL",
        "image_url": payload["image_url"],
        "thumbnail_url": payload["thumbnail_url"],
        "image_source_url": payload["image_source_url"],
        "source_credit": payload["source_credit"],
        "license_note": payload["license_note"],
        "curator_note": payload["curator_note"],
    }
    enrichment_payload = {
        "image": {
            "image_url": payload["image_url"],
            "thumbnail_url": payload["thumbnail_url"],
            "image_source_url": payload["image_source_url"],
            "source_credit": payload["source_credit"],
            "license_note": payload["license_note"],
            "intended_role": payload["intended_role"],
            "category_hint": payload["category_hint"],
            "indoor_outdoor_hint": payload["indoor_outdoor_hint"],
        },
        "place_snapshot": {
            "place_id": place["place_id"],
            "name": place["name"],
            "region_1": place.get("region_1"),
            "region_2": place.get("region_2"),
            "visit_role": place.get("visit_role"),
            "first_image_url": place.get("first_image_url"),
            "first_image_thumb_url": place.get("first_image_thumb_url"),
        },
    }
    validation_payload = {
        "validation": {
            "place_exists": True,
            "image_url_valid": True,
            "duplicate_checked": True,
            "source_type": "MANUAL",
            "enrichment_type": "IMAGE",
        }
    }
    review_payload = {
        "review_status": "PENDING_REVIEW",
        "review_required": True,
        "review_reason": "manual image candidate requires curator review before promotion",
        "curator_note": payload["curator_note"],
        "intended_role": payload["intended_role"],
        "source_credit": payload["source_credit"],
        "license_note": payload["license_note"],
    }
    return {
        "source_payload": source_payload,
        "enrichment_payload": enrichment_payload,
        "validation_payload": validation_payload,
        "review_payload": review_payload,
    }


def create_run(conn, place: dict[str, Any], *, dry_run: bool) -> str | None:
    if dry_run:
        return None
    run_id = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO place_enrichment_runs (
                run_id, enrichment_type, source_type, status,
                target_region, target_role, candidate_count, metadata
            )
            VALUES (%s, 'IMAGE', 'MANUAL', 'VALID', %s, %s, 1, %s)
            """,
            (
                run_id,
                place.get("region_1"),
                place.get("visit_role"),
                psycopg2.extras.Json(
                    {
                        "workflow": "manual_image_candidate",
                        "dry_run": False,
                        "promote": False,
                    }
                ),
            ),
        )
    return run_id


def insert_candidate(conn, run_id: str, place: dict[str, Any], payload: dict[str, Any]) -> int:
    payloads = build_payloads(place, payload)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO place_enrichment_candidates (
                run_id, place_id, enrichment_type, source_type, source_place_id,
                source_category, source_confidence, image_url, thumbnail_url,
                image_quality_score, business_status, validity_status, indoor_outdoor,
                validation_status, promote_status, review_status,
                is_selected, is_place_valid,
                source_payload, enrichment_payload, validation_payload, review_payload
            )
            VALUES (
                %(run_id)s, %(place_id)s, 'IMAGE', 'MANUAL', %(source_place_id)s,
                %(source_category)s, 1.000, %(image_url)s, %(thumbnail_url)s,
                NULL, 'UNKNOWN', 'VALID', %(indoor_outdoor)s,
                'VALID', 'PENDING', 'PENDING_REVIEW',
                FALSE, TRUE,
                %(source_payload)s, %(enrichment_payload)s, %(validation_payload)s, %(review_payload)s
            )
            RETURNING candidate_id
            """,
            {
                "run_id": run_id,
                "place_id": payload["place_id"],
                "source_place_id": source_place_id_for(payload["image_url"]),
                "source_category": payload["category_hint"],
                "image_url": payload["image_url"],
                "thumbnail_url": payload["thumbnail_url"],
                "indoor_outdoor": payload["indoor_outdoor_hint"],
                "source_payload": psycopg2.extras.Json(payloads["source_payload"]),
                "enrichment_payload": psycopg2.extras.Json(payloads["enrichment_payload"]),
                "validation_payload": psycopg2.extras.Json(payloads["validation_payload"]),
                "review_payload": psycopg2.extras.Json(payloads["review_payload"]),
            },
        )
        return int(cur.fetchone()[0])


def add_manual_image_candidate(args: argparse.Namespace) -> dict[str, Any]:
    payload = validate_inputs(args)
    conn = db_client.get_connection()
    try:
        place = fetch_place(conn, payload["place_id"])
        if not place:
            raise ManualImageCandidateError(f"place_id does not exist: {payload['place_id']}")

        duplicate = find_duplicate(conn, payload["image_url"])
        if duplicate:
            return {
                "status": "SKIPPED",
                "dry_run": args.dry_run,
                "reason": "DUPLICATE_IMAGE_URL",
                "duplicate": duplicate,
                "candidate_id": None,
                "run_id": None,
                "place": place,
            }

        payloads = build_payloads(place, payload)
        if args.dry_run:
            return {
                "status": "VALID",
                "dry_run": True,
                "candidate_id": None,
                "run_id": None,
                "place": place,
                "source_place_id": source_place_id_for(payload["image_url"]),
                **payloads,
            }

        run_id = create_run(conn, place, dry_run=False)
        candidate_id = insert_candidate(conn, run_id, place, payload)
        conn.commit()
        return {
            "status": "INSERTED",
            "dry_run": False,
            "candidate_id": candidate_id,
            "run_id": run_id,
            "place": place,
            "source_place_id": source_place_id_for(payload["image_url"]),
            **payloads,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add a manual IMAGE enrichment candidate for an existing place.")
    parser.add_argument("--place-id", type=int, required=True)
    parser.add_argument("--image-url", required=True)
    parser.add_argument("--thumbnail-url")
    parser.add_argument("--image-source-url")
    parser.add_argument("--source-credit")
    parser.add_argument("--license-note")
    parser.add_argument("--curator-note")
    parser.add_argument("--intended-role", default="primary", choices=sorted(VALID_INTENDED_ROLES))
    parser.add_argument("--category-hint")
    parser.add_argument("--indoor-outdoor-hint", choices=sorted(VALID_INDOOR_OUTDOOR))
    parser.add_argument("--dry-run", action="store_true", help="Validate and print payload without inserting.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = add_manual_image_candidate(args)
    except ManualImageCandidateError as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
