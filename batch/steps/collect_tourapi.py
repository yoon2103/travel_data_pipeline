from __future__ import annotations

from .common import StepResult


def run(context: dict) -> StepResult:
    """Skeleton incremental TourAPI collection step."""
    return StepResult(
        name="collect_tourapi",
        status="SKIPPED",
        message="dry-run skeleton: no TourAPI calls executed",
        metadata={"last_sync_time": context.get("last_sync_time")},
    )
