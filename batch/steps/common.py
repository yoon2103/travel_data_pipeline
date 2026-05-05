from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class StepResult:
    name: str
    status: str = "SUCCESS"
    input_count: int = 0
    output_count: int = 0
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class PipelineStop(RuntimeError):
    """Raised when a batch step must stop the pipeline."""
