"""Traceable provenance required for durable MEDAR memory."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MemoryOrigin(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    IMPORTED = "IMPORTED"


@dataclass(frozen=True)
class MemoryProvenance:
    source_id: str
    origin: MemoryOrigin
    recorded_at: datetime
    tenant_id: str
    user_id: str
    context_id: str
    confidence: float

    def __post_init__(self) -> None:
        for name in ("source_id", "tenant_id", "user_id", "context_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if not isinstance(self.origin, MemoryOrigin):
            raise TypeError("origin must be MemoryOrigin")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between zero and one")
