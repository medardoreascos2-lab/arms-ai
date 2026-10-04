"""R118C forget requests are authenticated, scoped, and truthfully incomplete."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.medar.memory_access import MemoryPurpose
from backend.medar.memory_forget_request import (
    ForgetRequestStatus, MemoryForgetRequest, submit_memory_forget_request,
)
from backend.medar.trusted_runtime_identity import (
    LocalAdminIdentityAuthority, LocalIdentityAssignment, RuntimeMemoryPermission,
)
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


NOW = datetime(2026, 10, 5, 3, tzinfo=timezone.utc)


def _setup():
    authority = LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-test-token"),
        LocalIdentityAssignment(
            "owner-a", "tenant-a", "session-a", "medar-local",
            MemoryPurpose.TECHNICAL_ASSISTANCE,
            frozenset({RuntimeMemoryPermission.READ, RuntimeMemoryPermission.WRITE}),
        ),
        clock=lambda: NOW,
    )
    return authority, authority.issue("synthetic-test-token")


def test_forget_request_enumerates_pending_layers_without_claiming_deletion():
    authority, identity = _setup()
    request = MemoryForgetRequest(
        "forget-1", "tenant-a", "owner-a", ("memory-1", "memory-2"),
        "user requested removal", NOW,
    )
    receipt = submit_memory_forget_request(
        authority, identity, request,
        known_storage_layers=("memory_db", "backup", "vector_index"),
    )
    assert receipt.status is ForgetRequestStatus.REQUIRES_STORAGE_REVIEW
    assert receipt.pending_storage_layers == ("backup", "memory_db", "vector_index")
    assert receipt.deleted_memory_ids == ()
    assert not receipt.asynchronous_deletion_complete


def test_cross_owner_request_is_denied():
    authority, identity = _setup()
    request = MemoryForgetRequest(
        "forget-1", "tenant-a", "other", ("memory-1",), "remove", NOW,
    )
    with pytest.raises(PermissionError):
        submit_memory_forget_request(
            authority, identity, request, known_storage_layers=("memory_db",),
        )


def test_request_cannot_claim_completion_or_hide_unknown_layers():
    request = MemoryForgetRequest(
        "forget-1", "tenant-a", "owner-a", ("memory-1",), "remove", NOW,
    )
    with pytest.raises(ValueError):
        replace(request, deletion_completed=True)
    authority, identity = _setup()
    with pytest.raises(ValueError):
        submit_memory_forget_request(
            authority, identity, request, known_storage_layers=(),
        )
    with pytest.raises(PermissionError):
        replace(request, reason="api_key: synthetic")
