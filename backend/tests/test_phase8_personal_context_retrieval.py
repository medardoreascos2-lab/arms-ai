"""R109C authenticated current-session personal context tests."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.medar.durable_memory_record import DurableMemoryDomain
from backend.medar.long_term_goal_memory import SessionGoalTracker
from backend.medar.memory_access import MemoryPurpose
from backend.medar.memory_candidates import CandidateSource, CandidateSourceType, MemoryCandidateExtractor
from backend.medar.personal_context_retrieval import resolve_personal_context
from backend.medar.session_working_memory import SessionWorkingMemory
from backend.medar.trusted_runtime_identity import LocalAdminIdentityAuthority, LocalIdentityAssignment, RuntimeMemoryPermission
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _setup(*, purpose=MemoryPurpose.PERSONALIZATION):
    authority = LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-test-token"),
        LocalIdentityAssignment("owner-a", "tenant-a", "session-a", "medar-local",
                                purpose, frozenset({RuntimeMemoryPermission.READ})),
        clock=lambda: NOW,
    )
    identity = authority.issue("synthetic-test-token")
    candidate = MemoryCandidateExtractor().extract(CandidateSource(
        "tenant-a", "owner-a", "conversation-1/turn-2", CandidateSourceType.USER_STATEMENT,
        DurableMemoryDomain.PREFERENCES, "I prefer style: concise synthetic replies",
    )).candidates[0]
    session = SessionWorkingMemory("session-a", "tenant-a", "owner-a")
    session.add_candidate(candidate)
    goals = SessionGoalTracker("tenant-a", "owner-a", "session-a")
    goal = goals.add_explicit("Goal: finish synthetic project", "conversation-1/turn-1")
    return authority, identity, session.snapshot(), (goal,)


def test_preference_and_project_resolution_is_scoped_and_source_linked():
    authority, identity, snapshot, goals = _setup()
    preference = resolve_personal_context(authority, identity, snapshot, "What is my preference?", goals=goals)
    assert [item.content for item in preference.evidence] == ["I prefer style: concise synthetic replies"]
    assert preference.evidence[0].source_reference == "conversation-1/turn-2"
    project = resolve_personal_context(authority, identity, snapshot, "How is my project?", goals=goals)
    assert [item.content for item in project.evidence] == ["finish synthetic project"]
    assert project.evidence[0].source_reference == "conversation-1/turn-1"
    assert preference.evidence[0].content not in repr(preference.evidence[0])
    assert project.evidence[0].content not in repr(project.evidence[0])
    assert preference.current_session_only and not preference.durable_read_performed
    assert not preference.persistence_performed


def test_last_time_has_explicit_durable_gap_and_no_unrequested_retrieval():
    authority, identity, snapshot, goals = _setup()
    historical = resolve_personal_context(authority, identity, snapshot, "What happened last time?", goals=goals)
    assert historical.evidence == ()
    assert historical.reason_code == "HISTORICAL_DURABLE_PERSONAL_MEMORY_UNAVAILABLE"
    no_trigger = resolve_personal_context(authority, identity, snapshot, "Hello", goals=goals)
    assert no_trigger.evidence == ()
    assert no_trigger.reason_code == "NO_PERSONAL_CONTEXT_TRIGGER"


def test_wrong_session_owner_tenant_or_purpose_is_denied():
    authority, identity, snapshot, goals = _setup()
    for forged in (
        replace(identity, owner_id="other"), replace(identity, tenant_id="other"),
        replace(identity, session_id="other"),
    ):
        with pytest.raises(PermissionError):
            resolve_personal_context(authority, forged, snapshot, "my preference", goals=goals)
    with pytest.raises(PermissionError):
        resolve_personal_context(authority, identity, replace(snapshot, owner_id="other"), "my preference", goals=goals)
    technical_authority, technical_identity, _, _ = _setup(purpose=MemoryPurpose.TECHNICAL_ASSISTANCE)
    with pytest.raises(PermissionError):
        resolve_personal_context(technical_authority, technical_identity, snapshot, "my preference", goals=goals)
