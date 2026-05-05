from __future__ import annotations

from .common import StepResult


def run(context: dict) -> StepResult:
    """Skeleton normalization step."""
    return StepResult(
        name="normalize_places",
        status="SKIPPED",
        message="dry-run skeleton: no clean_places rows generated",
    )
