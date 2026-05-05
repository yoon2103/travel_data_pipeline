from __future__ import annotations

from .common import StepResult


def run(context: dict) -> StepResult:
    """Skeleton production upsert step.

    promote defaults to False. This step must never modify places unless
    promote=True, dry_run=False, QA passed, and smoke succeeds.
    """
    if context.get("dry_run") or not context.get("promote"):
        return StepResult(
            name="promote_places",
            status="SKIPPED",
            message="places upsert skipped because dry_run=true or promote=false",
        )
    return StepResult(
        name="promote_places",
        status="SKIPPED",
        message="promote implementation pending",
    )
