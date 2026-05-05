from __future__ import annotations

from .common import StepResult


def run(context: dict) -> StepResult:
    """Skeleton raw_places load step."""
    return StepResult(
        name="load_raw_places",
        status="SKIPPED",
        message="dry-run skeleton: no raw_places rows inserted",
    )
