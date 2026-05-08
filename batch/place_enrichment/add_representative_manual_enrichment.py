from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config  # noqa: E402,F401
import db_client  # noqa: E402
from batch.place_enrichment.image_qa_policy import (  # noqa: E402
    grade_image_quality,
    is_placeholder_url,
    qa_payload,
)


VALID_INTENDED_ROLES = {"primary", "gallery"}
ENRICHMENT_IMAGE = "REPRESENTATIVE_IMAGE"
ENRICHMENT_OVERVIEW = "REPRESENTATIVE_OVERVIEW"


class RepresentativeManualEnrichmentError(ValueError):
    def __init__(self, message: str, *, code: str = "VALIDATION_ERROR", details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def validate_url(value: str | None, *, field_name: str, required: bool = False) -> str | None:
    value = (value or "").strip()
    if not value:
        if required:
            raise RepresentativeManualEnrichmentError(f"{field_name} is required")
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RepresentativeManualEnrichmentError(f"{field_name} must be an absolute http(s) URL")
    return value


def validate_image_source_url(value: str | None) -> str:
    value = (value or "").strip()
    if not value:
        raise RepresentativeManualEnrichmentError(
            "image_source_url is required for representative image",
            code="IMAGE_SOURCE_URL_REQUIRED",
        )
    parsed = urlparse(value)
    allowed_schemes = {"http", "https", "operator-upload", "s3", "gs"}
    if parsed.scheme not in allowed_schemes or not parsed.netloc:
        raise RepresentativeManualEnrichmentError(
            "image_source_url must be http(s), operator-upload, s3, or gs URL",
            code="INVALID_IMAGE_SOURCE_URL",
            details={"image_source_url": value, "allowed_schemes": sorted(allowed_schemes)},
        )
    return value


def require_text(value: str | None, *, field_name: str) -> str:
    value = (value or "").strip()
    if not value:
        raise RepresentativeManualEnrichmentError(
            f"{field_name} is required for representative image",
            code=f"{field_name.upper()}_REQUIRED",
        )
    return value


def validate_positive_int(value: int | None, *, field_name: str) -> int | None:
    if value is None:
        return None
    if value <= 0:
        raise RepresentativeManualEnrichmentError(
            f"{field_name} must be a positive integer",
            code="INVALID_IMAGE_METADATA",
            details={field_name: value},
        )
    return value


def validate_mime_type(value: str | None) -> str | None:
    value = (value or "").strip().lower()
    if not value:
        return None
    if not value.startswith("image/") or len(value.split("/", 1)[1]) == 0:
        raise RepresentativeManualEnrichmentError(
            "mime_type must start with image/",
            code="INVALID_MIME_TYPE",
            details={"mime_type": value},
        )
    return value


def validate_checksum(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    raw = value.split("sha256:", 1)[1] if value.lower().startswith("sha256:") else value
    if not re.fullmatch(r"[a-fA-F0-9]{64}", raw):
        raise RepresentativeManualEnrichmentError(
            "checksum must be a SHA-256 hex digest, optionally prefixed with sha256:",
            code="INVALID_CHECKSUM",
            details={"checksum": value},
        )
    return f"sha256:{raw.lower()}"


def normalize_overview(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    return " ".join(value.split())


def hash_value(*parts: str | None) -> str:
    raw = "|".join(part or "" for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def fetch_approved_representative(conn, expected_name: str) -> dict[str, Any] | None:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                candidate_id,
                expected_poi_name,
                region_1,
                region_2,
                source_type,
                source_name,
                source_place_id,
                confidence_score,
                review_status,
                promote_status,
                latitude,
                longitude,
                address,
                road_address
            FROM representative_poi_candidates
            WHERE expected_poi_name = %s
              AND review_status = 'APPROVED'
              AND COALESCE(category, '') NOT IN ('REPRESENTATIVE_IMAGE', 'REPRESENTATIVE_OVERVIEW')
            ORDER BY confidence_score DESC NULLS LAST, candidate_id
            LIMIT 1
            """,
            (expected_name,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def expected_name_exists(conn, expected_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM representative_poi_candidates WHERE expected_poi_name = %s LIMIT 1",
            (expected_name,),
        )
        return cur.fetchone() is not None


def find_duplicate_image(conn, expected_name: str, image_url: str) -> dict[str, Any] | None:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT candidate_id, expected_poi_name, source_type, source_name, review_status, promote_status
            FROM representative_poi_candidates
            WHERE expected_poi_name = %s
              AND image_url = %s
            ORDER BY created_at DESC, candidate_id DESC
            LIMIT 1
            """,
            (expected_name, image_url),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def find_duplicate_checksum(conn, expected_name: str, checksum: str | None) -> dict[str, Any] | None:
    if not checksum:
        return None
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT candidate_id, expected_poi_name, source_type, source_name,
                   review_status, promote_status,
                   source_payload->'enrichment_payload'->'representative_image'->>'checksum' AS checksum
            FROM representative_poi_candidates
            WHERE expected_poi_name = %s
              AND source_type = 'MANUAL'
              AND category = 'REPRESENTATIVE_IMAGE'
              AND source_payload->'enrichment_payload'->'representative_image'->>'checksum' = %s
            ORDER BY created_at DESC, candidate_id DESC
            LIMIT 1
            """,
            (expected_name, checksum),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def build_image_payload(args: argparse.Namespace) -> dict[str, Any] | None:
    if not args.image_url:
        return None
    image_url = validate_url(args.image_url, field_name="image_url", required=True)
    if is_placeholder_url(image_url):
        raise RepresentativeManualEnrichmentError(
            "placeholder image domains are not allowed",
            code="PLACEHOLDER_IMAGE_URL",
            details={"image_url": image_url},
        )
    thumbnail_url = validate_url(args.thumbnail_url, field_name="thumbnail_url")
    if thumbnail_url and is_placeholder_url(thumbnail_url):
        raise RepresentativeManualEnrichmentError(
            "placeholder thumbnail domains are not allowed",
            code="PLACEHOLDER_THUMBNAIL_URL",
            details={"thumbnail_url": thumbnail_url},
        )
    image_source_url = validate_image_source_url(args.image_source_url)
    source_credit = require_text(args.source_credit, field_name="source_credit")
    license_note = require_text(args.license_note, field_name="license_note")
    intended_role = (args.intended_role or "primary").strip().lower()
    if intended_role not in VALID_INTENDED_ROLES:
        raise RepresentativeManualEnrichmentError(f"intended_role must be one of {sorted(VALID_INTENDED_ROLES)}")
    width = validate_positive_int(args.width, field_name="width")
    height = validate_positive_int(args.height, field_name="height")
    mime_type = validate_mime_type(args.mime_type)
    checksum = validate_checksum(args.checksum)

    quality_probe = {
        "risk_flags": [],
        "source_validity": "VALID",
        "license_validity": "VALID",
        "width": width,
        "height": height,
        "landmark_identifiable": True if args.landmark_identifiable else None,
    }
    return {
        "enrichment_type": ENRICHMENT_IMAGE,
        "image_url": image_url,
        "thumbnail_url": thumbnail_url,
        "image_source_url": image_source_url,
        "source_credit": source_credit,
        "license_note": license_note,
        "curator_note": (args.curator_note or "").strip() or None,
        "intended_role": intended_role,
        "quality_note": (args.quality_note or "").strip() or None,
        "width": width,
        "height": height,
        "mime_type": mime_type,
        "checksum": checksum,
        "landmark_identifiable": True if args.landmark_identifiable else None,
        "quality_level": grade_image_quality(quality_probe),
    }


def build_overview_payload(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.overview is None:
        return None
    overview = normalize_overview(args.overview)
    if not overview:
        raise RepresentativeManualEnrichmentError("overview must not be empty")
    return {
        "enrichment_type": ENRICHMENT_OVERVIEW,
        "overview_text": overview,
        "source_credit": (args.source_credit or "").strip() or None,
        "curator_note": (args.curator_note or "").strip() or None,
        "summary_length": len(overview),
        "language": "ko",
    }


def build_candidate_payloads(
    representative: dict[str, Any],
    enrichment: dict[str, Any],
) -> dict[str, Any]:
    enrichment_type = enrichment["enrichment_type"]
    expected_name = representative["expected_poi_name"]
    representative_snapshot = json_safe(representative)
    base_payload = {
        "workflow": "representative_manual_enrichment",
        "enrichment_type": enrichment_type,
        "expected_poi_name": expected_name,
        "approved_representative_candidate_id": representative["candidate_id"],
        "source_type": "MANUAL",
    }
    source_payload = {
        **base_payload,
        "source_credit": enrichment.get("source_credit"),
        "curator_note": enrichment.get("curator_note"),
    }

    if enrichment_type == ENRICHMENT_IMAGE:
        quality_summary = {
            "quality_level": enrichment.get("quality_level"),
            "width": enrichment.get("width"),
            "height": enrichment.get("height"),
            "mime_type": enrichment.get("mime_type"),
            "checksum": enrichment.get("checksum"),
            "source_validity": "VALID",
            "license_validity": "VALID",
            "metadata_complete": all(
                enrichment.get(key) is not None for key in ("width", "height", "mime_type", "checksum")
            ),
            "metadata_extraction": "USER_PROVIDED",
        }
        enrichment_payload = {
            "representative_image": {
                "image_url": enrichment["image_url"],
                "thumbnail_url": enrichment.get("thumbnail_url"),
                "image_source_url": enrichment.get("image_source_url"),
                "source_credit": enrichment.get("source_credit"),
                "license_note": enrichment.get("license_note"),
                "intended_role": enrichment.get("intended_role"),
                "quality_note": enrichment.get("quality_note"),
                "quality_level": enrichment.get("quality_level"),
                "landmark_identifiable": enrichment.get("landmark_identifiable"),
                "width": enrichment.get("width"),
                "height": enrichment.get("height"),
                "mime_type": enrichment.get("mime_type"),
                "checksum": enrichment.get("checksum"),
            },
            "approved_representative_snapshot": representative_snapshot,
        }
        risk_flags = []
    else:
        enrichment_payload = {
            "representative_overview": {
                "overview_text": enrichment["overview_text"],
                "source_credit": enrichment.get("source_credit"),
                "curator_note": enrichment.get("curator_note"),
                "summary_length": enrichment.get("summary_length"),
                "language": enrichment.get("language"),
            },
            "approved_representative_snapshot": representative_snapshot,
        }
        risk_flags = ["IMAGE_MISSING"]

    validation_payload = {
        "enrichment_type": enrichment_type,
        "risk_flags": risk_flags,
        "validation_result": "MANUAL_ENRICHMENT_PENDING_REVIEW",
        "quality_level": enrichment.get("quality_level"),
        "quality_summary": quality_summary if enrichment_type == ENRICHMENT_IMAGE else None,
        "approved_representative_candidate_exists": True,
        "places_write": False,
        "seed_write": False,
        "promote": False,
    }
    review_payload = {
        "review_status": "PENDING_REVIEW",
        "review_required": True,
        "review_reason": f"{enrichment_type} requires curator review before any promote.",
        "curator_note": enrichment.get("curator_note"),
        "source_credit": enrichment.get("source_credit"),
        "license_note": enrichment.get("license_note"),
        "quality_level": enrichment.get("quality_level"),
        "quality_summary": quality_summary if enrichment_type == ENRICHMENT_IMAGE else None,
        "enrichment_type": enrichment_type,
    }
    source_payload["enrichment_payload"] = enrichment_payload
    if enrichment_type == ENRICHMENT_IMAGE:
        source_payload["quality_summary"] = quality_summary
    return {
        "source_payload": source_payload,
        "enrichment_payload": enrichment_payload,
        "validation_payload": validation_payload,
        "review_payload": review_payload,
    }


def insert_manual_candidate(
    conn,
    representative: dict[str, Any],
    enrichment: dict[str, Any],
) -> int:
    payloads = build_candidate_payloads(representative, enrichment)
    enrichment_type = enrichment["enrichment_type"]
    expected_name = representative["expected_poi_name"]
    digest = hash_value(expected_name, enrichment_type, enrichment.get("image_url"), enrichment.get("overview_text"))
    source_place_id = f"manual-{enrichment_type.lower()}:{digest[:32]}"
    source_name = f"{expected_name} manual {enrichment_type.lower()} {digest[:8]}"

    image_url = enrichment.get("image_url")
    thumbnail_url = enrichment.get("thumbnail_url")
    overview = enrichment.get("overview_text")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO representative_poi_candidates (
                expected_poi_name,
                region_1,
                region_2,
                matched_place_id,
                source_type,
                source_place_id,
                source_name,
                category,
                address,
                road_address,
                latitude,
                longitude,
                phone,
                image_url,
                overview,
                confidence_score,
                representative_status,
                review_status,
                promote_status,
                source_payload,
                validation_payload,
                review_payload
            )
            VALUES (
                %(expected_poi_name)s,
                %(region_1)s,
                %(region_2)s,
                NULL,
                'MANUAL',
                %(source_place_id)s,
                %(source_name)s,
                %(category)s,
                %(address)s,
                %(road_address)s,
                %(latitude)s,
                %(longitude)s,
                NULL,
                %(image_url)s,
                %(overview)s,
                100.00,
                'CANDIDATE',
                'PENDING_REVIEW',
                'PENDING',
                %(source_payload)s,
                %(validation_payload)s,
                %(review_payload)s
            )
            ON CONFLICT DO NOTHING
            RETURNING candidate_id
            """,
            {
                "expected_poi_name": expected_name,
                "region_1": representative["region_1"],
                "region_2": representative.get("region_2"),
                "source_place_id": source_place_id,
                "source_name": source_name,
                "category": enrichment_type,
                "address": representative.get("address"),
                "road_address": representative.get("road_address"),
                "latitude": representative.get("latitude"),
                "longitude": representative.get("longitude"),
                "image_url": image_url,
                "overview": overview,
                "source_payload": psycopg2.extras.Json(payloads["source_payload"]),
                "validation_payload": psycopg2.extras.Json(payloads["validation_payload"]),
                "review_payload": psycopg2.extras.Json(payloads["review_payload"]),
            },
        )
        row = cur.fetchone()
        if not row:
            return 0
        return int(row[0])


def add_manual_enrichment(args: argparse.Namespace) -> dict[str, Any]:
    expected_name = (args.expected_poi_name or "").strip()
    if not expected_name:
        raise RepresentativeManualEnrichmentError("expected_poi_name is required")

    image_payload = build_image_payload(args)
    overview_payload = build_overview_payload(args)
    if not image_payload and not overview_payload:
        raise RepresentativeManualEnrichmentError("at least one of image_url or overview is required")

    conn = db_client.get_connection()
    try:
        if not expected_name_exists(conn, expected_name):
            raise RepresentativeManualEnrichmentError(f"expected_poi_name does not exist in staging: {expected_name}")

        representative = fetch_approved_representative(conn, expected_name)
        if not representative:
            raise RepresentativeManualEnrichmentError(
                f"approved representative candidate does not exist: {expected_name}"
            )

        results = []
        for enrichment in [p for p in (image_payload, overview_payload) if p]:
            if enrichment["enrichment_type"] == ENRICHMENT_IMAGE:
                duplicate = find_duplicate_image(conn, expected_name, enrichment["image_url"])
                if duplicate:
                    results.append(
                        {
                            "status": "SKIPPED",
                            "reason": "DUPLICATE_IMAGE_URL",
                            "enrichment_type": ENRICHMENT_IMAGE,
                            "duplicate": duplicate,
                            "candidate_id": None,
                        }
                    )
                    continue
                checksum_duplicate = find_duplicate_checksum(conn, expected_name, enrichment.get("checksum"))
                if checksum_duplicate:
                    results.append(
                        {
                            "status": "SKIPPED",
                            "reason": "DUPLICATE_IMAGE_CHECKSUM",
                            "enrichment_type": ENRICHMENT_IMAGE,
                            "duplicate": checksum_duplicate,
                            "candidate_id": None,
                        }
                    )
                    continue

            payloads = build_candidate_payloads(representative, enrichment)
            if enrichment["enrichment_type"] == ENRICHMENT_IMAGE:
                qa = qa_payload(
                    {
                        "image_url": enrichment["image_url"],
                        "source_payload": payloads["source_payload"],
                        "validation_payload": payloads["validation_payload"],
                        "review_payload": payloads["review_payload"],
                    },
                    duplicate_count=0,
                )
                payloads["validation_payload"]["quality_summary"] = qa
                payloads["source_payload"]["quality_summary"] = qa
            if args.dry_run:
                results.append(
                    {
                        "status": "VALID",
                        "dry_run": True,
                        "enrichment_type": enrichment["enrichment_type"],
                        "candidate_id": None,
                        "payloads": payloads,
                    }
                )
                continue

            candidate_id = insert_manual_candidate(conn, representative, enrichment)
            if candidate_id:
                results.append(
                    {
                        "status": "INSERTED",
                        "dry_run": False,
                        "enrichment_type": enrichment["enrichment_type"],
                        "candidate_id": candidate_id,
                    }
                )
            else:
                results.append(
                    {
                        "status": "SKIPPED",
                        "dry_run": False,
                        "reason": "DUPLICATE_OR_CONFLICT",
                        "enrichment_type": enrichment["enrichment_type"],
                        "candidate_id": None,
                    }
                )

        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()

        return {
            "status": "OK",
            "dry_run": args.dry_run,
            "expected_poi_name": expected_name,
            "approved_representative_candidate_id": representative["candidate_id"],
            "results": results,
            "places_changed": False,
            "seed_changed": False,
            "promote_executed": False,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add manual representative POI image/overview enrichment candidate.")
    parser.add_argument("--expected-poi-name", required=True)
    parser.add_argument("--image-url")
    parser.add_argument("--thumbnail-url")
    parser.add_argument("--image-source-url")
    parser.add_argument("--overview")
    parser.add_argument("--curator-note")
    parser.add_argument("--source-credit")
    parser.add_argument("--license-note")
    parser.add_argument("--intended-role", default="primary", choices=sorted(VALID_INTENDED_ROLES))
    parser.add_argument("--quality-note")
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--mime-type")
    parser.add_argument("--checksum")
    parser.add_argument("--landmark-identifiable", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = add_manual_enrichment(args)
    except RepresentativeManualEnrichmentError as exc:
        print(
            json.dumps(
                {"status": "ERROR", "error_code": exc.code, "reason": str(exc), "details": exc.details},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
