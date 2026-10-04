"""R113A ROSITA knowledge persistence is encrypted, scoped, and local only."""

from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from backend.medar.bound_memory_access import BoundMemoryRequest
from backend.medar.durable_memory_encryption import AESGCMEphemeralMemoryEncryption
from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableSensitivity, RetentionPolicy,
)
from backend.medar.encrypted_memory_envelope import open_memory_content
from backend.medar.memory_access import MemoryPurpose
from backend.medar.rosita_knowledge_memory import (
    RositaKnowledgeKind, RositaKnowledgeMemory, RositaKnowledgeWriteAuthority,
)
from backend.medar.sqlite_encrypted_memory_store import SQLiteEncryptedMemoryStore
from backend.medar.sqlite_memory_store import MemoryScope
from backend.medar.trusted_runtime_identity import (
    LocalAdminIdentityAuthority, LocalIdentityAssignment, RuntimeMemoryPermission,
)
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def _record(**changes):
    values = dict(
        knowledge_id="rosita-1", tenant_id="tenant-a", owner_id="owner-a",
        session_id="session-a", source_reference="synthetic-test:rosita-note-1",
        kind=RositaKnowledgeKind.NOTE, title="synthetic family note",
        content="synthetic authorized knowledge",
        evidence_references=("synthetic-test:evidence-1",), observed_at=NOW,
    )
    values.update(changes)
    return RositaKnowledgeMemory(**values)


def _setup():
    identity_authority = LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-test-token"),
        LocalIdentityAssignment(
            "owner-a", "tenant-a", "session-a", "medar-local",
            MemoryPurpose.RESEARCH,
            frozenset({RuntimeMemoryPermission.READ, RuntimeMemoryPermission.WRITE}),
        ), clock=lambda: NOW,
    )
    identity = identity_authority.issue("synthetic-test-token")
    request = BoundMemoryRequest(
        "owner-a", "tenant-a", "session-a", "medar-local",
        DurableMemoryDomain.ROSITA, DurableSensitivity.HIGHLY_SENSITIVE,
        MemoryPurpose.RESEARCH,
    )
    provider = AESGCMEphemeralMemoryEncryption(local_development_enabled=True)
    authority = RositaKnowledgeWriteAuthority(
        identity_authority, provider, local_development_enabled=True,
    )
    return authority, identity, request, provider


class SpyWriter:
    def __init__(self):
        self.calls = []

    def write(self, scope, envelope):
        self.calls.append((scope, envelope))


@pytest.mark.parametrize("kind", tuple(RositaKnowledgeKind))
def test_rosita_supports_each_required_knowledge_kind(kind):
    record = _record(kind=kind)
    assert record.kind is kind
    assert record.domain is DurableMemoryDomain.ROSITA
    assert record.sensitivity is DurableSensitivity.HIGHLY_SENSITIVE
    assert record.user_authorized and record.local_development_only
    assert not record.external_sharing_authority
    assert record.content not in repr(record)


def test_approved_rosita_knowledge_persists_only_encrypted_content(tmp_path):
    authority, identity, request, provider = _setup()
    record = _record()
    approval = authority.approve(identity, request, record, RetentionPolicy.LONG_TERM)
    path = tmp_path / "rosita.db"
    try:
        with SQLiteEncryptedMemoryStore(path, read_only=False) as store:
            receipt = authority.persist(
                identity, request, record, RetentionPolicy.LONG_TERM, approval, store,
            )
        assert receipt.local_development_only and not receipt.external_sharing_authorized
        assert record.content.encode() not in path.read_bytes()
        with SQLiteEncryptedMemoryStore(path) as store:
            envelope = store.get(MemoryScope("tenant-a", "owner-a"), record.knowledge_id, 1)
        assert envelope is not None and envelope.content_hash is None
        plaintext = open_memory_content(
            envelope, provider, memory_id=record.knowledge_id,
            owner_id="owner-a", tenant_id="tenant-a",
            domain=DurableMemoryDomain.ROSITA,
            sensitivity=DurableSensitivity.HIGHLY_SENSITIVE, version=1,
        )
        assert json.loads(plaintext) == json.loads(record.serialized_content())
    finally:
        provider.close()


def test_rejected_rosita_writes_have_zero_store_calls():
    authority, identity, request, provider = _setup()
    record = _record()
    approval = authority.approve(identity, request, record, RetentionPolicy.LONG_TERM)
    writer = SpyWriter()
    try:
        for changed_request, changed_record, retention, changed_approval in (
            (replace(request, owner_id="other"), record, RetentionPolicy.LONG_TERM, approval),
            (replace(request, tenant_id="other"), record, RetentionPolicy.LONG_TERM, approval),
            (replace(request, claimed_role="family"), record, RetentionPolicy.LONG_TERM, approval),
            (request, record, RetentionPolicy.SESSION, approval),
            (request, replace(record, content="changed"), RetentionPolicy.LONG_TERM, approval),
            (request, record, RetentionPolicy.LONG_TERM, None),
        ):
            with pytest.raises(PermissionError):
                authority.persist(
                    identity, changed_request, changed_record, retention,
                    changed_approval, writer,
                )
        assert writer.calls == []
    finally:
        provider.close()


def test_rosita_rejects_unapproved_real_or_secret_like_content():
    with pytest.raises(PermissionError):
        _record(user_authorized=False)
    with pytest.raises(PermissionError):
        _record(source_reference="real-source")
    with pytest.raises(PermissionError):
        _record(content="api_key: synthetic")
    with pytest.raises(PermissionError):
        _record(external_sharing_authority=True)
