from __future__ import annotations

from .common import StepResult


def run(context: dict) -> StepResult:
    """Skeleton DB backup step.

    The first implementation only records intent. The actual pg_dump command
    should be wired in after the EC2 backup path and retention policy are fixed.
    """
    if context.get("dry_run"):
        return StepResult(
            name="backup_db",
            status="SKIPPED",
            message="dry-run: backup command not executed",
        )
    return StepResult(
        name="backup_db",
        status="SKIPPED",
        message="backup implementation pending",
    )
