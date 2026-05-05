from __future__ import annotations

from .common import StepResult


def run(context: dict) -> StepResult:
    """Skeleton staging load step."""
    return StepResult(
        name="load_staging_places",
        status="SKIPPED",
        message="dry-run skeleton: staging load not executed",
        metadata={"staging_requires_ai_fields": True},
    )
