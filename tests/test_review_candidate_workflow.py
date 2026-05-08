from __future__ import annotations

from batch.place_enrichment.review_candidate import build_review_payload


def test_build_review_payload_preserves_previous_fields_and_appends_history():
    payload = {"review_required": True, "review_status": "PENDING_REVIEW"}

    updated = build_review_payload(
        payload,
        reviewer_id="ops_001",
        action="approve",
        note="good cafe interior",
        previous_status="PENDING_REVIEW",
        reviewed_at="2026-05-08T00:00:00+00:00",
    )

    assert updated["review_required"] is True
    assert updated["reviewer_id"] == "ops_001"
    assert updated["review_action"] == "approve"
    assert updated["review_note"] == "good cafe interior"
    assert updated["previous_status"] == "PENDING_REVIEW"
    assert len(updated["review_history"]) == 1


def test_build_review_payload_keeps_review_history():
    payload = {
        "review_history": [
            {
                "reviewer_id": "ops_000",
                "reviewed_at": "2026-05-07T00:00:00+00:00",
                "review_action": "skip",
                "review_note": "old",
                "previous_status": "PENDING_REVIEW",
            }
        ]
    }

    updated = build_review_payload(
        payload,
        reviewer_id="ops_001",
        action="reject",
        note="bad image",
        previous_status="IN_REVIEW",
        reviewed_at="2026-05-08T00:00:00+00:00",
    )

    assert len(updated["review_history"]) == 2
    assert updated["review_history"][-1]["review_action"] == "reject"
