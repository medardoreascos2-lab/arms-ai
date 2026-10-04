"""Scoped advisory memory for known tool failures before retry planning."""

from dataclasses import dataclass, field
from datetime import datetime

from backend.medar.memory_candidates import has_secret_like_content
from backend.medar.request import CognitiveDomain
from backend.medar.tool_contract import ToolResultStatus
from backend.medar.tool_performance import ToolFailureClass, ToolPerformanceEvent


@dataclass(frozen=True)
class KnownToolFailure:
    failure_id: str
    tenant_id: str
    owner_id: str
    tool_id: str
    domain: CognitiveDomain
    task_type: str
    failure_class: ToolFailureClass
    issue_code: str
    issue_summary: str = field(repr=False)
    recovery_guidance: str = field(repr=False)
    evidence_event_id: str
    observed_at: datetime
    retry_authority: bool = False
    tool_authority: bool = False

    def __post_init__(self) -> None:
        for name in (
            "failure_id", "tenant_id", "owner_id", "tool_id", "task_type",
            "issue_code", "issue_summary", "recovery_guidance", "evidence_event_id",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 512:
                raise ValueError(f"{name} must be bounded non-empty text")
            if has_secret_like_content(value):
                raise PermissionError("secret-like tool failure content is not retained")
        if not isinstance(self.domain, CognitiveDomain) or not isinstance(self.failure_class, ToolFailureClass):
            raise TypeError("tool failure domain and class must be typed")
        if self.failure_class is ToolFailureClass.NONE:
            raise ValueError("known tool failure requires a failure class")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("tool failure time must be timezone-aware")
        if self.retry_authority or self.tool_authority:
            raise ValueError("tool failure memory cannot authorize retry or tool use")


def known_failure_from_event(
    event: ToolPerformanceEvent,
    *,
    failure_id: str,
    issue_code: str,
    issue_summary: str,
    recovery_guidance: str,
) -> KnownToolFailure:
    if not isinstance(event, ToolPerformanceEvent):
        raise TypeError("tool performance event is required")
    if event.status is ToolResultStatus.SUCCESS or event.failure_class is ToolFailureClass.NONE:
        raise ValueError("only failed or blocked tool events can become failure memory")
    return KnownToolFailure(
        failure_id, event.tenant_id, event.owner_id, event.tool_id,
        event.domain, event.task_type, event.failure_class, issue_code,
        issue_summary, recovery_guidance, event.event_id, event.observed_at,
    )


class ToolFailureMemory:
    def __init__(self) -> None:
        self._failures: dict[str, KnownToolFailure] = {}

    def remember(self, failure: KnownToolFailure) -> None:
        if not isinstance(failure, KnownToolFailure):
            raise TypeError("known tool failure is required")
        if failure.failure_id in self._failures:
            raise ValueError("known tool failure already exists")
        self._failures[failure.failure_id] = failure

    def before_retry(
        self,
        *,
        tenant_id: str,
        owner_id: str,
        tool_id: str,
        domain: CognitiveDomain,
        task_type: str,
    ) -> tuple[KnownToolFailure, ...]:
        if not isinstance(domain, CognitiveDomain):
            raise TypeError("tool failure query domain must be typed")
        for name, value in (
            ("tenant_id", tenant_id), ("owner_id", owner_id),
            ("tool_id", tool_id), ("task_type", task_type),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be bounded non-empty text")
        return tuple(sorted(
            (
                failure for failure in self._failures.values()
                if failure.tenant_id == tenant_id and failure.owner_id == owner_id
                and failure.tool_id == tool_id and failure.domain is domain
                and failure.task_type == task_type
            ),
            key=lambda failure: (failure.observed_at, failure.failure_id),
            reverse=True,
        ))
