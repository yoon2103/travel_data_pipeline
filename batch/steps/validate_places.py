from __future__ import annotations

from .common import StepResult


def run(context: dict) -> StepResult:
    """Skeleton validation step."""
    return StepResult(
        name="validate_places",
        status="SKIPPED",
        message="dry-run skeleton: no invalid_places rows generated",
    )
