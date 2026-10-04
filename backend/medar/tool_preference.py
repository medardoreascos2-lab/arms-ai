"""Evidence-based advisory tool preferences with no authorization effect."""

from dataclasses import dataclass

from backend.medar.request import CognitiveDomain
from backend.medar.tool_performance import ToolPerformanceSummary


@dataclass(frozen=True)
class ToolPreferenceCandidate:
    tool_id: str
    attempts: int
    success_rate: float
    average_latency_ms: float


@dataclass(frozen=True)
class ToolPreferenceRecommendation:
    tenant_id: str
    owner_id: str
    domain: CognitiveDomain
    task_type: str
    recommended_tool_id: str | None
    candidates: tuple[ToolPreferenceCandidate, ...]
    reason_codes: tuple[str, ...]
    observed_events: int
    tool_authority_granted: bool = False
    new_permission_granted: bool = False

    def __post_init__(self) -> None:
        if self.tool_authority_granted or self.new_permission_granted:
            raise ValueError("tool preference cannot grant authority or permission")


def recommend_tools(
    summaries: tuple[ToolPerformanceSummary, ...],
    *,
    tenant_id: str,
    owner_id: str,
    domain: CognitiveDomain,
    task_type: str,
    minimum_attempts: int = 2,
) -> ToolPreferenceRecommendation:
    if not isinstance(summaries, tuple) or any(not isinstance(item, ToolPerformanceSummary) for item in summaries):
        raise TypeError("typed tool performance summaries are required")
    if isinstance(minimum_attempts, bool) or not isinstance(minimum_attempts, int) or not 1 <= minimum_attempts <= 1000:
        raise ValueError("minimum attempts must be from 1 to 1000")
    if not isinstance(domain, CognitiveDomain):
        raise TypeError("tool preference domain must be typed")
    for name, value in (("tenant_id", tenant_id), ("owner_id", owner_id), ("task_type", task_type)):
        if not isinstance(value, str) or not value.strip() or len(value) > 240:
            raise ValueError(f"{name} must be bounded non-empty text")
    if any(
        item.tenant_id != tenant_id or item.owner_id != owner_id
        or item.domain is not domain or item.task_type != task_type
        for item in summaries
    ):
        raise PermissionError("tool preference evidence scope mismatch")
    if len({item.tool_id for item in summaries}) != len(summaries):
        raise ValueError("tool preference summaries must be unique by tool")
    eligible = tuple(item for item in summaries if item.attempts >= minimum_attempts)
    ranked = tuple(sorted(
        eligible,
        key=lambda item: (-item.success_rate, item.average_latency_ms, -item.attempts, item.tool_id),
    ))
    candidates = tuple(
        ToolPreferenceCandidate(item.tool_id, item.attempts, item.success_rate, item.average_latency_ms)
        for item in ranked
    )
    if not candidates:
        return ToolPreferenceRecommendation(
            tenant_id, owner_id, domain, task_type, None, (),
            ("INSUFFICIENT_OBSERVED_EVIDENCE",), sum(item.attempts for item in summaries),
        )
    return ToolPreferenceRecommendation(
        tenant_id, owner_id, domain, task_type, candidates[0].tool_id, candidates,
        ("OBSERVED_SUCCESS_RATE", "OBSERVED_LATENCY_TIEBREAK"),
        sum(item.attempts for item in eligible),
    )
