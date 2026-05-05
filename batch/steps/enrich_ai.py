from __future__ import annotations

from .common import StepResult


def run(context: dict) -> StepResult:
    """Skeleton AI enrichment step.

    Staging promotion must reject rows without visit_role, ai_tags, ai_summary,
    estimated_duration, and visit_time_slot.
    """
    return StepResult(
        name="enrich_ai",
        status="SKIPPED",
        message="dry-run skeleton: no AI calls executed",
        metadata={
            "required_fields": [
                "visit_role",
                "ai_tags",
                "ai_summary",
                "estimated_duration",
                "visit_time_slot",
            ]
        },
    )
