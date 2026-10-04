"""Bounded selection of already-authorized MEDAR memory evidence."""

from dataclasses import dataclass

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_reranking import RerankedMemoryEvidence, RerankedMemoryResult


@dataclass(frozen=True)
class MemoryContextBudget:
    max_tokens: int
    max_memories: int
    domain_token_limits: dict[DurableMemoryDomain, int]
    allowed_sensitivities: frozenset[DurableSensitivity] = frozenset({DurableSensitivity.PUBLIC})

    def __post_init__(self) -> None:
        if isinstance(self.max_tokens, bool) or not isinstance(self.max_tokens, int) or self.max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        if isinstance(self.max_memories, bool) or not isinstance(self.max_memories, int) or self.max_memories < 1:
            raise ValueError("max_memories must be positive")
        if not isinstance(self.domain_token_limits, dict) or any(
            not isinstance(domain, DurableMemoryDomain)
            or isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
            for domain, limit in self.domain_token_limits.items()
        ):
            raise ValueError("domain token limits must be positive and typed")
        if not isinstance(self.allowed_sensitivities, frozenset) or not self.allowed_sensitivities or any(
            not isinstance(value, DurableSensitivity) for value in self.allowed_sensitivities
        ):
            raise ValueError("allowed sensitivities must be an explicit non-empty typed set")
        if not self.allowed_sensitivities <= frozenset({DurableSensitivity.PUBLIC, DurableSensitivity.INTERNAL}):
            raise PermissionError("sensitive memory context requires validated production encryption")


@dataclass(frozen=True)
class BudgetedMemoryEvidence:
    evidence: RerankedMemoryEvidence
    reserved_tokens: int

    @property
    def memory_id(self) -> str:
        return self.evidence.memory_id


@dataclass(frozen=True)
class MemoryContextSelection:
    selected: tuple[BudgetedMemoryEvidence, ...]
    reserved_tokens: int
    skipped: tuple[tuple[str, str], ...]
    heuristic_token_reservation: bool = True
    persistence_performed: bool = False

    def __post_init__(self) -> None:
        if not self.heuristic_token_reservation or self.persistence_performed:
            raise ValueError("budget selection is an in-memory estimate, not persistence")


def _reservation(candidate: RerankedMemoryEvidence) -> int:
    record = candidate.record
    # Each UTF-8 byte reserves one token plus fixed framing. This is deliberately
    # conservative for common subword tokenizers, not a tokenizer-specific count.
    fields = (record.content, record.memory_id, record.source_reference, record.domain.value)
    return sum(len(value.encode("utf-8")) for value in fields) + 32


def select_memory_context(result: RerankedMemoryResult, budget: MemoryContextBudget) -> MemoryContextSelection:
    if not isinstance(result, RerankedMemoryResult) or not isinstance(budget, MemoryContextBudget):
        raise TypeError("reranked evidence and a context budget are required")
    selected: list[BudgetedMemoryEvidence] = []
    skipped: list[tuple[str, str]] = []
    used = 0
    domain_used: dict[DurableMemoryDomain, int] = {}
    for candidate in result.evidence:
        record = candidate.record
        if record.sensitivity not in budget.allowed_sensitivities:
            skipped.append((record.memory_id, "SENSITIVITY_BLOCKED"))
            continue
        domain_limit = budget.domain_token_limits.get(record.domain)
        if domain_limit is None:
            skipped.append((record.memory_id, "DOMAIN_NOT_BUDGETED"))
            continue
        reserve = _reservation(candidate)
        if len(selected) >= budget.max_memories:
            skipped.append((record.memory_id, "MEMORY_COUNT_EXCEEDED"))
        elif reserve > budget.max_tokens - used:
            skipped.append((record.memory_id, "TOTAL_TOKEN_BUDGET_EXCEEDED"))
        elif reserve > domain_limit - domain_used.get(record.domain, 0):
            skipped.append((record.memory_id, "DOMAIN_TOKEN_BUDGET_EXCEEDED"))
        else:
            selected.append(BudgetedMemoryEvidence(candidate, reserve))
            used += reserve
            domain_used[record.domain] = domain_used.get(record.domain, 0) + reserve
    return MemoryContextSelection(tuple(selected), used, tuple(skipped))
