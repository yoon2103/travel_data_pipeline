from __future__ import annotations

import argparse

from batch.place_enrichment.add_manual_image_candidate import (
    ManualImageCandidateError,
    build_payloads,
    source_place_id_for,
    validate_inputs,
    validate_url,
)


def make_args(**overrides):
    values = {
        "place_id": 123,
        "image_url": "https://example.com/place.jpg",
        "thumbnail_url": "https://example.com/place-thumb.jpg",
        "image_source_url": "https://example.com/source",
        "source_credit": "Example",
        "license_note": "curator confirmed",
        "curator_note": "good exterior image",
        "intended_role": "primary",
        "category_hint": "cafe",
        "indoor_outdoor_hint": "indoor",
        "dry_run": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_validate_inputs_accepts_valid_payload():
    payload = validate_inputs(make_args())

    assert payload["place_id"] == 123
    assert payload["image_url"] == "https://example.com/place.jpg"
    assert payload["intended_role"] == "primary"
    assert payload["indoor_outdoor_hint"] == "indoor"


def test_validate_inputs_rejects_empty_image_url():
    try:
        validate_inputs(make_args(image_url=""))
    except ManualImageCandidateError:
        return
    raise AssertionError("empty image_url should be rejected")


def test_validate_inputs_rejects_invalid_image_url():
    try:
        validate_inputs(make_args(image_url="not-a-url"))
    except ManualImageCandidateError:
        return
    raise AssertionError("invalid image_url should be rejected")


def test_validate_inputs_rejects_invalid_intended_role():
    try:
        validate_inputs(make_args(intended_role="cover"))
    except ManualImageCandidateError:
        return
    raise AssertionError("invalid intended_role should be rejected")


def test_source_place_id_is_stable_without_exposing_url():
    first = source_place_id_for("https://example.com/place.jpg")
    second = source_place_id_for("https://example.com/place.jpg")

    assert first == second
    assert first.startswith("manual-image:")
    assert "example.com" not in first


def test_payload_shape_for_review_and_enrichment():
    place = {
        "place_id": 123,
        "name": "Manual Cafe",
        "region_1": "서울",
        "region_2": "1",
        "visit_role": "cafe",
        "first_image_url": None,
        "first_image_thumb_url": None,
    }
    payload = validate_inputs(make_args())

    payloads = build_payloads(place, payload)

    assert payloads["source_payload"]["source_type"] == "MANUAL"
    assert payloads["enrichment_payload"]["image"]["intended_role"] == "primary"
    assert payloads["validation_payload"]["validation"]["place_exists"] is True
    assert payloads["review_payload"]["review_status"] == "PENDING_REVIEW"
