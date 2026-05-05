from __future__ import annotations

from .common import StepResult


def run(context: dict) -> StepResult:
    """Skeleton API smoke test step."""
    return StepResult(
        name="smoke_test",
        status="SKIPPED",
        message="dry-run skeleton: API smoke test not executed",
        metadata={"checks": ["regions", "generate", "limited", "blocked", "extend"]},
    )
