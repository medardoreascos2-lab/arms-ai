"""Redacted MEDAR cognitive trace without hidden reasoning storage."""

from dataclasses import dataclass
from hashlib import sha256

from backend.medar.uncertainty import UncertaintyLevel


@dataclass(frozen=True)
class CognitiveTrace:
    request_id: str
    request_digest: str
    intent_summary: str
    plan_id: str | None
    agent_ids: tuple[str, ...]
    tool_call_ids: tuple[str, ...]
    memory_read_ids: tuple[str, ...]
    result_status: str
    uncertainty: UncertaintyLevel
    failures: tuple[str, ...]
    hidden_chain_of_thought_stored: bool = False

    def __post_init__(self) -> None:
        if not self.request_id.strip() or len(self.request_digest) != 64:
            raise ValueError("trace requires request identity and SHA-256 digest")
        if self.hidden_chain_of_thought_stored:
            raise ValueError("hidden chain-of-thought must never be stored")


def build_cognitive_trace(
    *,
    request_id: str,
    normalized_request: str,
    intent_summary: str,
    plan_id: str | None,
    agent_ids: tuple[str, ...],
    tool_call_ids: tuple[str, ...],
    memory_read_ids: tuple[str, ...],
    result_status: str,
    uncertainty: UncertaintyLevel,
    failures: tuple[str, ...] = (),
) -> CognitiveTrace:
    digest = sha256(normalized_request.encode("utf-8")).hexdigest()
    return CognitiveTrace(
        request_id, digest, intent_summary, plan_id, agent_ids, tool_call_ids,
        memory_read_ids, result_status, uncertainty, failures,
    )
