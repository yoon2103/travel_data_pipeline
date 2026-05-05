from __future__ import annotations

from .common import StepResult


def run(context: dict) -> StepResult:
    """Skeleton QA step."""
    return StepResult(
        name="run_qa",
        status="SKIPPED",
        message="dry-run skeleton: QA not executed",
        metadata={"checks": ["course_quality", "place_count_distribution"]},
    )
