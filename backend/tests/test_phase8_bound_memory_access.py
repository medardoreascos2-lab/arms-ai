"""R108E identity-bound memory reads deny spoofing before store access."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.medar.bound_memory_access import BoundMemoryAccess, BoundMemoryRequest
from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_access import MemoryPurpose
from backend.medar.trusted_runtime_identity import LocalAdminIdentityAuthority, LocalIdentityAssignment, RuntimeMemoryPermission
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


class SpyStore:
    def __init__(self):
        self.calls = []

    def get(self, scope, memory_id):
        self.calls.append(("get", scope, memory_id))
        return None

    def search(self, scope, query, domains, limit=10):
        self.calls.append(("search", scope, query))
        return ()

    def list_active(self, scope, domain, sensitivity, max_records):
        self.calls.append(("list_active", scope, domain))
        return ()


def _setup(clock=lambda: NOW):
    authority = LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-test-token"),
        LocalIdentityAssignment(
            "owner-a", "tenant-a", "session-a", "medar-local",
            MemoryPurpose.TECHNICAL_ASSISTANCE,
            frozenset({RuntimeMemoryPermission.READ}),
        ),
        clock=clock,
    )
    identity = authority.issue("synthetic-test-token")
    store = SpyStore()
    facade = BoundMemoryAccess(authority, store)
    request = BoundMemoryRequest(
        "owner-a", "tenant-a", "session-a", "medar-local",
        DurableMemoryDomain.TECHNICAL, DurableSensitivity.PUBLIC,
        MemoryPurpose.TECHNICAL_ASSISTANCE,
    )
    return authority, identity, store, facade, request


def test_bound_read_uses_issued_scope_and_read_only_permission():
    _, identity, store, facade, request = _setup()
    assert facade.get(identity, request, "memory-1") is None
    assert facade.search(identity, request, "schema") == ()
    assert facade.list_active(identity, request) == ()
    assert [call[0] for call in store.calls] == ["get", "search", "list_active"]
    assert all(call[1].tenant_id == "tenant-a" and call[1].owner_id == "owner-a" for call in store.calls)
    assert not hasattr(facade, "write")


@pytest.mark.parametrize("change", [
    {"owner_id": "owner-b"}, {"tenant_id": "tenant-b"},
    {"session_id": "session-b"}, {"service_id": "other-service"},
    {"purpose": MemoryPurpose.RESEARCH},
    {"domain": DurableMemoryDomain.FINANCIAL},
    {"sensitivity": DurableSensitivity.PERSONAL},
    {"claimed_permission": RuntimeMemoryPermission.WRITE},
    {"claimed_role": "admin"},
])
def test_spoofed_scope_or_escalation_is_denied_before_store(change):
    _, identity, store, facade, request = _setup()
    with pytest.raises(PermissionError):
        facade.get(identity, replace(request, **change), "memory-1")
    assert store.calls == []


def test_expired_and_foreign_issued_identities_are_denied_before_store():
    current = [NOW]
    authority, identity, store, facade, request = _setup(clock=lambda: current[0])
    current[0] = NOW + timedelta(minutes=16)
    with pytest.raises(PermissionError):
        facade.get(identity, request, "memory-1")
    assert store.calls == []
    _, foreign, _, _, _ = _setup()
    with pytest.raises(PermissionError):
        facade.get(foreign, request, "memory-1")
    assert store.calls == []
