"""Traceable MEDAR outcome events with no execution or learning authority."""

from dataclasses import dataclass, field
from datetime import datetime

from backend.medar.memory_candidates import has_secret_like_content


@dataclass(frozen=True)
class OutcomeEvent:
    event_id: str
    tenant_id: str
    owner_id: str
    session_id: str
    source_reference: str
    task: str = field(repr=False)
    decision: str = field(repr=False)
    prediction: str = field(repr=False)
    expected_result: str = field(repr=False)
    observed_result: str = field(repr=False)
    success_metric: str = field(repr=False)
    error: str | None = field(default=None, repr=False)
    timestamp: datetime = field(default=None)
    execution_authority: bool = False
    model_update_authority: bool = False

    def __post_init__(self) -> None:
        for name in ("event_id", "tenant_id", "owner_id", "session_id", "source_reference"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be a bounded explicit reference")
        for name in (
            "task", "decision", "prediction", "expected_result",
            "observed_result", "success_metric",
        ):
            self._validate_content(getattr(self, name), name)
        if self.error is not None:
            self._validate_content(self.error, "error")
        if not isinstance(self.timestamp, datetime) or self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("outcome timestamp must be timezone-aware")
        if self.execution_authority or self.model_update_authority:
            raise ValueError("outcome events cannot authorize execution or model updates")

    @staticmethod
    def _validate_content(value: str, name: str) -> None:
        if not isinstance(value, str) or not value.strip() or len(value) > 2048:
            raise ValueError(f"{name} must be bounded explicit text")
        if has_secret_like_content(value):
            raise PermissionError("secret-like outcome content is not retained")
