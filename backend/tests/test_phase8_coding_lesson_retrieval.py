"""R110C relevant prior failure lessons remain scoped and advisory."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.medar.coding_lesson_retrieval import retrieve_failure_lessons
from backend.medar.coding_outcome_memory import CodingOutcomeMemory, CodingOutcomeStatus
from backend.medar.memory_access import MemoryPurpose
from backend.medar.trusted_runtime_identity import LocalAdminIdentityAuthority, LocalIdentityAssignment, RuntimeMemoryPermission
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _setup():
    authority = LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-test-token"),
        LocalIdentityAssignment("owner-a", "tenant-a", "session-a", "medar-local",
                                MemoryPurpose.TECHNICAL_ASSISTANCE,
                                frozenset({RuntimeMemoryPermission.READ})),
        clock=lambda: NOW,
    )
    identity = authority.issue("synthetic-test-token")
    failure = CodingOutcomeMemory(
        "tenant-a", "owner-a", "session-a", "source-failure",
        "schema migration checksum", "apply migration", ("migration.py",),
        ("pytest failed",), CodingOutcomeStatus.FAILURE,
        "checksum mismatch", "verify schema checksum before retry", NOW,
    )
    success = replace(failure, source_reference="source-success", status=CodingOutcomeStatus.SUCCESS,
                      tests=("pytest passed",))
    return authority, identity, failure, success


def test_relevant_prior_failure_is_returned_with_source_and_no_action_authority():
    authority, identity, failure, success = _setup()
    result = retrieve_failure_lessons(authority, identity, (failure, success), "schema checksum")
    assert len(result.lessons) == 1
    assert result.lessons[0].source_reference == "source-failure"
    assert result.lessons[0].lesson == "verify schema checksum before retry"
    assert result.lessons[0].relevance > 0
    assert result.lessons[0].lesson not in repr(result.lessons[0])
    assert not result.lessons[0].code_modification_authority
    assert not result.durable_read_performed and not result.external_call_performed


def test_unrelated_or_cross_scope_failure_is_not_retrieved():
    authority, identity, failure, _ = _setup()
    assert retrieve_failure_lessons(authority, identity, (failure,), "visual layout").lessons == ()
    with pytest.raises(PermissionError):
        retrieve_failure_lessons(authority, identity, (replace(failure, owner_id="other"),), "schema")
    with pytest.raises(PermissionError):
        retrieve_failure_lessons(authority, replace(identity, tenant_id="other"), (failure,), "schema")
