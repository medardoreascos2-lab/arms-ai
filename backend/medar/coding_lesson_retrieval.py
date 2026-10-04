"""Scoped lexical retrieval of prior session coding-failure lessons."""

import re
from dataclasses import dataclass, field

from backend.medar.coding_outcome_memory import CodingOutcomeMemory, CodingOutcomeStatus
from backend.medar.memory_access import MemoryPurpose
from backend.medar.trusted_runtime_identity import (
    LocalAdminIdentityAuthority, RuntimeMemoryPermission, TrustedRuntimeIdentity,
)


def _terms(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.casefold(), flags=re.UNICODE))


@dataclass(frozen=True)
class CodingFailureLesson:
    source_reference: str
    task: str = field(repr=False)
    root_cause: str = field(repr=False)
    lesson: str = field(repr=False)
    relevance: float = 0.0
    session_only: bool = True
    code_modification_authority: bool = False

    def __post_init__(self) -> None:
        if not 0 < self.relevance <= 1 or not self.session_only or self.code_modification_authority:
            raise ValueError("failure lesson must be relevant and nonauthoritative")


@dataclass(frozen=True)
class CodingLessonResult:
    lessons: tuple[CodingFailureLesson, ...]
    reason_code: str
    durable_read_performed: bool = False
    external_call_performed: bool = False

    def __post_init__(self) -> None:
        if self.durable_read_performed or self.external_call_performed:
            raise ValueError("lesson retrieval is session-local")


def retrieve_failure_lessons(
    authority: LocalAdminIdentityAuthority,
    identity: TrustedRuntimeIdentity,
    outcomes: tuple[CodingOutcomeMemory, ...],
    task_query: str,
    *,
    limit: int = 5,
) -> CodingLessonResult:
    if not isinstance(authority, LocalAdminIdentityAuthority):
        raise TypeError("trusted authority is required")
    authority.require_valid(identity)
    if identity.purpose is not MemoryPurpose.TECHNICAL_ASSISTANCE or RuntimeMemoryPermission.READ not in identity.permissions:
        raise PermissionError("technical read authority is required")
    if not isinstance(outcomes, tuple) or len(outcomes) > 1000:
        raise ValueError("bounded outcome tuple is required")
    if not isinstance(task_query, str) or not task_query.strip() or len(task_query) > 1024:
        raise ValueError("bounded task query is required")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be 1 to 100")
    query_terms = _terms(task_query)
    if not query_terms or len(query_terms) > 64:
        raise ValueError("task query must contain 1 to 64 terms")
    matches: list[CodingFailureLesson] = []
    for outcome in outcomes:
        if not isinstance(outcome, CodingOutcomeMemory) or (
            outcome.tenant_id != identity.tenant_id
            or outcome.owner_id != identity.owner_id
            or outcome.session_id != identity.session_id
        ):
            raise PermissionError("coding outcome scope mismatch")
        if outcome.status is not CodingOutcomeStatus.FAILURE:
            continue
        task_overlap = len(query_terms & _terms(outcome.task)) / len(query_terms)
        detail_overlap = len(query_terms & _terms(outcome.root_cause + " " + outcome.lesson)) / len(query_terms)
        relevance = 0.7 * task_overlap + 0.3 * detail_overlap
        if relevance > 0:
            matches.append(CodingFailureLesson(
                outcome.source_reference, outcome.task, outcome.root_cause,
                outcome.lesson, relevance,
            ))
    matches.sort(key=lambda item: (-item.relevance, item.source_reference))
    return CodingLessonResult(tuple(matches[:limit]), "MATCHED_SESSION_FAILURES" if matches else "NO_PRIOR_FAILURE_MATCH")
