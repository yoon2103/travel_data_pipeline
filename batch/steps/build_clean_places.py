from __future__ import annotations

from .common import StepResult


def run(context: dict) -> StepResult:
    """Skeleton clean_places materialization step."""
    return StepResult(
        name="build_clean_places",
        status="SKIPPED",
        message="dry-run skeleton: clean_places build not executed",
    )
