"""User-authorized, session-only life advisory memory with narrow content limits."""

from dataclasses import dataclass, field
from datetime import datetime

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_candidates import has_secret_like_content


@dataclass(frozen=True)
class LifeAdvisoryMemory:
    tenant_id: str
    owner_id: str
    session_id: str
    source_reference: str
    authorization_reference: str
    goals: tuple[str, ...] = field(repr=False)
    priorities: tuple[str, ...] = field(repr=False)
    decision: str = field(repr=False)
    outcome: str | None = field(repr=False)
    observed_at: datetime
    domain: DurableMemoryDomain = DurableMemoryDomain.LIFE
    sensitivity: DurableSensitivity = DurableSensitivity.PERSONAL
    user_authorized: bool = True
    contains_intimate_details: bool = False
    session_only: bool = True
    advisory_only: bool = True
    action_authority: bool = False

    def __post_init__(self) -> None:
        for name in (
            "tenant_id", "owner_id", "session_id", "source_reference",
            "authorization_reference",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be a bounded explicit reference")
        for name in ("goals", "priorities"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or not 1 <= len(values) <= 20:
                raise ValueError(f"{name} must contain one to twenty entries")
            for value in values:
                self._validate_content(value, name)
        self._validate_content(self.decision, "decision")
        if self.outcome is not None:
            self._validate_content(self.outcome, "outcome")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observation time must be timezone-aware")
        if self.domain is not DurableMemoryDomain.LIFE or self.sensitivity is not DurableSensitivity.PERSONAL:
            raise ValueError("life advisory classification cannot be weakened")
        if not self.user_authorized or self.contains_intimate_details:
            raise PermissionError("life advisory memory requires authorization and excludes intimate details")
        if not self.session_only or not self.advisory_only or self.action_authority:
            raise ValueError("life advisory memory cannot authorize actions or durable storage")

    @staticmethod
    def _validate_content(value: str, name: str) -> None:
        if not isinstance(value, str) or not value.strip() or len(value) > 1024:
            raise ValueError(f"{name} must be bounded explicit text")
        if has_secret_like_content(value):
            raise PermissionError("secret-like life advisory content is not retained")
