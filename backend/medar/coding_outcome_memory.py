"""Structured, source-linked coding outcomes for session-only MEDAR learning."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from backend.medar.memory_candidates import has_secret_like_content


class CodingOutcomeStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True)
class CodingOutcomeMemory:
    tenant_id: str
    owner_id: str
    session_id: str
    source_reference: str
    task: str = field(repr=False)
    approach: str = field(repr=False)
    files: tuple[str, ...] = field(repr=False)
    tests: tuple[str, ...] = field(repr=False)
    status: CodingOutcomeStatus
    root_cause: str = field(repr=False)
    lesson: str = field(repr=False)
    observed_at: datetime
    session_only: bool = True
    persistence_authorized: bool = False
    code_modification_authority: bool = False

    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "session_id", "source_reference"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        for name in ("task", "approach", "root_cause", "lesson"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 1024:
                raise ValueError(f"{name} must be bounded explicit text")
            if has_secret_like_content(value):
                raise PermissionError("secret-like coding outcome is not retained")
        for name in ("files", "tests"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or len(values) > 100 or any(
                not isinstance(value, str) or not value.strip() or len(value) > 240 or has_secret_like_content(value)
                for value in values
            ):
                raise ValueError(f"{name} must be bounded source-linked strings")
        if not isinstance(self.status, CodingOutcomeStatus):
            raise TypeError("coding outcome status must be explicit")
        if self.status is CodingOutcomeStatus.SUCCESS and not self.tests:
            raise ValueError("successful outcome requires test evidence")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("coding outcome time must be timezone-aware")
        if not self.session_only or self.persistence_authorized or self.code_modification_authority:
            raise ValueError("coding outcome cannot persist or modify code")
