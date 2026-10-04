"""Identity-scoped current-session personal context resolution.

Cross-session durable personal retrieval remains unavailable without production
memory encryption. No store or external service is called here.
"""

import re
from dataclasses import field, dataclass

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_access import MemoryPurpose
from backend.medar.memory_candidates import has_secret_like_content
from backend.medar.long_term_goal_memory import GoalState, SessionGoal
from backend.medar.preference_memory import propose_explicit_preference
from backend.medar.session_working_memory import WorkingMemorySnapshot
from backend.medar.trusted_runtime_identity import LocalAdminIdentityAuthority, RuntimeMemoryPermission, TrustedRuntimeIdentity


_PERSONAL_DOMAINS = frozenset({
    DurableMemoryDomain.PERSONAL, DurableMemoryDomain.PREFERENCES,
    DurableMemoryDomain.LIFE, DurableMemoryDomain.CAREER,
})


@dataclass(frozen=True)
class PersonalContextEvidence:
    item_id: str
    category: str
    content: str = field(repr=False)
    source_reference: str
    session_id: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value.strip() for value in (
            self.item_id, self.category, self.content, self.source_reference, self.session_id,
        )):
            raise ValueError("personal context evidence must be source-linked")


@dataclass(frozen=True)
class PersonalContextResult:
    evidence: tuple[PersonalContextEvidence, ...]
    reason_code: str
    current_session_only: bool = True
    durable_read_performed: bool = False
    persistence_performed: bool = False

    def __post_init__(self) -> None:
        if not self.current_session_only or self.durable_read_performed or self.persistence_performed:
            raise ValueError("personal context cannot claim durable access")


def resolve_personal_context(
    authority: LocalAdminIdentityAuthority,
    identity: TrustedRuntimeIdentity,
    snapshot: WorkingMemorySnapshot,
    request_text: str,
    *,
    goals: tuple[SessionGoal, ...] = (),
    max_items: int = 10,
) -> PersonalContextResult:
    if not isinstance(authority, LocalAdminIdentityAuthority):
        raise TypeError("identity authority is required")
    authority.require_valid(identity)
    if identity.purpose is not MemoryPurpose.PERSONALIZATION or RuntimeMemoryPermission.READ not in identity.permissions:
        raise PermissionError("personalization read authority is required")
    if not isinstance(snapshot, WorkingMemorySnapshot) or (
        identity.tenant_id != snapshot.tenant_id
        or identity.owner_id != snapshot.owner_id
        or identity.session_id != snapshot.session_id
    ):
        raise PermissionError("personal context session scope mismatch")
    if not isinstance(request_text, str) or not request_text.strip() or len(request_text) > 4096:
        raise ValueError("bounded request text is required")
    if type(max_items) is not int or not 1 <= max_items <= 100:
        raise ValueError("max_items must be 1 to 100")
    if not isinstance(goals, tuple):
        raise TypeError("goals must be a tuple")
    for goal in goals:
        if not isinstance(goal, SessionGoal) or (
            goal.tenant_id != identity.tenant_id or goal.owner_id != identity.owner_id
            or goal.session_id != identity.session_id
        ):
            raise PermissionError("goal scope mismatch")
    normalized = " ".join(request_text.casefold().split())
    preference_request = bool(re.search(r"\bmy preference\b", normalized))
    project_request = bool(re.search(r"\bmy project\b", normalized))
    remember_request = bool(re.search(r"\bremember\b", normalized))
    historical_request = bool(re.search(r"\blast time\b", normalized))
    if not any((preference_request, project_request, remember_request, historical_request)):
        return PersonalContextResult((), "NO_PERSONAL_CONTEXT_TRIGGER")
    items: list[PersonalContextEvidence] = []
    if preference_request or remember_request:
        for candidate in snapshot.candidate_durable:
            if (candidate.tenant_id, candidate.owner_id) != (identity.tenant_id, identity.owner_id):
                raise PermissionError("candidate scope mismatch")
            if candidate.domain not in _PERSONAL_DOMAINS:
                continue
            if candidate.sensitivity is not DurableSensitivity.PERSONAL or has_secret_like_content(candidate.content):
                raise PermissionError("personal candidate classification is unsafe")
            if preference_request:
                try:
                    propose_explicit_preference(candidate)
                except (TypeError, ValueError, PermissionError):
                    continue
            items.append(PersonalContextEvidence(
                candidate.candidate_id, "SESSION_CANDIDATE", candidate.content,
                candidate.source_reference, snapshot.session_id,
            ))
    if project_request or remember_request:
        for goal in goals:
            if goal.state in (GoalState.ACTIVE, GoalState.PAUSED):
                items.append(PersonalContextEvidence(
                    goal.goal_id, "SESSION_GOAL", goal.description,
                    goal.source_reference, snapshot.session_id,
                ))
    if historical_request and not items:
        return PersonalContextResult((), "HISTORICAL_DURABLE_PERSONAL_MEMORY_UNAVAILABLE")
    return PersonalContextResult(
        tuple(items[:max_items]),
        "CURRENT_SESSION_ONLY_HISTORICAL_UNAVAILABLE" if historical_request else "CURRENT_SESSION_ONLY",
    )
