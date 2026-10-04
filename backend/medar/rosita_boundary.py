"""Health response boundary for the Rosita knowledge agent."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.rosita_evidence import RositaHealthItem


class RositaOperation(str, Enum):
    RETRIEVE = "RETRIEVE"
    SUMMARIZE = "SUMMARIZE"
    COMPARE = "COMPARE"
    PRESERVE = "PRESERVE"


@dataclass(frozen=True)
class RositaHealthResponse:
    items: tuple[RositaHealthItem, ...]
    summary: str
    operations: tuple[RositaOperation, ...]
    treatment_validated: bool = False

    def __post_init__(self) -> None:
        if not self.items or not self.summary.strip():
            raise ValueError("health response requires items and a summary")
        if any(operation not in tuple(RositaOperation) for operation in self.operations):
            raise ValueError("unsupported Rosita operation")
        if self.treatment_validated:
            raise ValueError("Rosita content cannot validate medical treatment")


def build_rosita_health_response(
    items: tuple[RositaHealthItem, ...],
    summary: str,
    operations: tuple[RositaOperation, ...],
) -> RositaHealthResponse:
    return RositaHealthResponse(items, summary, operations)
