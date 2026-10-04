"""R104B policy denial before memory-store calls."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity, MemoryLifecycle
from backend.medar.memory_access import (
    AuthorizedMemoryStore, MemoryAccessContext, MemoryAgentPermission,
    MemoryPurpose,
)


class SpyStore:
    def __init__(self):
        self.calls = []
        self.record = SimpleNamespace(domain=DurableMemoryDomain.TECHNICAL, sensitivity=DurableSensitivity.INTERNAL, tenant_id="tenant-a", owner_id="owner-a", status=MemoryLifecycle.ACTIVE, expires_at=None)

    def get(self, scope, memory_id):
        self.calls.append(("get", scope, memory_id))
        return self.record

    def search(self, scope, query, domains, limit=10):
        self.calls.append(("search", scope, query))
        return (self.record,)

    def write(self, scope, record):
        self.calls.append(("write", scope, record))


def _context(**changes):
    fields = dict(
        requester_id="owner-a", requester_tenant_id="tenant-a",
        owner_id="owner-a", tenant_id="tenant-a",
        domain=DurableMemoryDomain.TECHNICAL,
        sensitivity=DurableSensitivity.INTERNAL,
        purpose=MemoryPurpose.TECHNICAL_ASSISTANCE,
        permission=MemoryAgentPermission.READ,
    )
    fields.update(changes)
    return MemoryAccessContext(**fields)


@pytest.mark.parametrize("changes", [
    {"requester_id": "other"},
    {"requester_tenant_id": "other"},
    {"purpose": MemoryPurpose.FINANCIAL_ANALYSIS},
    {"permission": MemoryAgentPermission.NONE},
    {"sensitivity": DurableSensitivity.HIGHLY_SENSITIVE},
])
def test_denied_read_never_touches_store(changes):
    spy = SpyStore()
    with pytest.raises(PermissionError):
        AuthorizedMemoryStore(spy).get(_context(**changes), "memory-1")
    assert spy.calls == []


def test_denied_write_never_touches_store():
    spy = SpyStore()
    facade = AuthorizedMemoryStore(spy)
    with pytest.raises(PermissionError):
        facade.write(_context(permission=MemoryAgentPermission.WRITE), spy.record)
    with pytest.raises(PermissionError):
        facade.write(_context(permission=MemoryAgentPermission.WRITE, persistence_approved=True, requester_id="other"), spy.record)
    assert spy.calls == []


def test_scoped_read_and_explicit_approved_write_delegate_once():
    spy = SpyStore()
    facade = AuthorizedMemoryStore(spy)
    assert facade.get(_context(), "memory-1") is spy.record
    assert facade.search(_context(), "safe") == (spy.record,)
    facade.write(_context(permission=MemoryAgentPermission.WRITE, persistence_approved=True), spy.record)
    assert [call[0] for call in spy.calls] == ["get", "search", "write"]
    assert all(call[1].tenant_id == "tenant-a" and call[1].owner_id == "owner-a" for call in spy.calls)


def test_store_classification_mismatch_is_not_disclosed():
    spy = SpyStore()
    spy.record = replace(_context(), sensitivity=DurableSensitivity.PUBLIC)
    with pytest.raises(PermissionError, match="classification"):
        AuthorizedMemoryStore(spy).get(_context(), "memory-1")


def test_inactive_memory_is_not_returned_to_normal_read():
    spy = SpyStore()
    spy.record.status = MemoryLifecycle.RETRACTED
    assert AuthorizedMemoryStore(spy).get(_context(), "memory-1") is None


def test_cross_scope_store_response_is_rejected():
    spy = SpyStore()
    spy.record.owner_id = "other"
    with pytest.raises(PermissionError, match="scope"):
        AuthorizedMemoryStore(spy).get(_context(), "memory-1")
