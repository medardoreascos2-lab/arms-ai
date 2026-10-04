"""R121F validates encrypted ROSITA knowledge continuity and access boundaries."""

from datetime import datetime, timezone
import json

from backend.medar.bound_memory_access import BoundMemoryRequest
from backend.medar.durable_memory_encryption import AESGCMEphemeralMemoryEncryption
from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity, RetentionPolicy
from backend.medar.encrypted_memory_envelope import open_memory_content
from backend.medar.memory_access import MemoryPurpose
from backend.medar.rosita_access_policy import RositaAccessLevel, RositaFamilyAccessPolicy, evaluate_future_family_access, evaluate_local_owner_access
from backend.medar.rosita_knowledge_memory import RositaKnowledgeKind, RositaKnowledgeMemory, RositaKnowledgeWriteAuthority, RositaProvenanceClass
from backend.medar.sqlite_encrypted_memory_store import SQLiteEncryptedMemoryStore
from backend.medar.sqlite_memory_store import MemoryScope
from backend.medar.trusted_runtime_identity import LocalAdminIdentityAuthority, LocalIdentityAssignment, RuntimeMemoryPermission
from backend.security.admin_authorization_v2 import AdminAuthorizationV2

NOW = datetime(2026, 10, 4, 22, 30, tzinfo=timezone.utc)


def test_rosita_knowledge_round_trips_encrypted_for_local_owner_while_family_share_stays_disabled(tmp_path):
    authority = LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-token"),
        LocalIdentityAssignment("owner-a", "tenant-a", "session-a", "medar-local", MemoryPurpose.RESEARCH, frozenset({RuntimeMemoryPermission.READ, RuntimeMemoryPermission.WRITE})),
        clock=lambda: NOW,
    )
    identity = authority.issue("synthetic-token")
    record = RositaKnowledgeMemory(
        "rosita-continuity-1", "tenant-a", "owner-a", "session-a", "synthetic-test:rosita-1",
        RositaKnowledgeKind.NOTE, RositaProvenanceClass.PERSONAL_EXPERIENCE,
        "synthetic continuity note", "synthetic authorized knowledge",
        ("synthetic-test:evidence-1",), NOW,
    )
    request = BoundMemoryRequest("owner-a", "tenant-a", "session-a", "medar-local", DurableMemoryDomain.ROSITA, DurableSensitivity.HIGHLY_SENSITIVE, MemoryPurpose.RESEARCH)
    policy = RositaFamilyAccessPolicy("owner-a", "tenant-a", RositaAccessLevel.FAMILY_AUTHORIZED, ("synthetic-test:family-approval-1",))
    path = tmp_path / "rosita.db"
    with AESGCMEphemeralMemoryEncryption(local_development_enabled=True) as crypto:
        writer = RositaKnowledgeWriteAuthority(authority, crypto, local_development_enabled=True)
        approval = writer.approve(identity, request, record, RetentionPolicy.LONG_TERM)
        with SQLiteEncryptedMemoryStore(path, read_only=False) as store:
            receipt = writer.persist(identity, request, record, RetentionPolicy.LONG_TERM, approval, store)
        with SQLiteEncryptedMemoryStore(path) as reopened:
            envelope = reopened.get(MemoryScope("tenant-a", "owner-a"), record.knowledge_id, 1)
        plaintext = open_memory_content(envelope, crypto, memory_id=record.knowledge_id, owner_id="owner-a", tenant_id="tenant-a", domain=DurableMemoryDomain.ROSITA, sensitivity=DurableSensitivity.HIGHLY_SENSITIVE, version=1)

    document = json.loads(plaintext)
    owner_access = evaluate_local_owner_access(authority, identity, policy)
    family_access = evaluate_future_family_access(policy, "synthetic-test:family-approval-1")
    assert document["provenance_classification"] == "PERSONAL_EXPERIENCE"
    assert document["evidence_references"] == ["synthetic-test:evidence-1"]
    assert record.content.encode() not in path.read_bytes()
    assert owner_access.allowed and owner_access.reason_code == "LOCAL_OWNER_ALLOWED"
    assert not family_access.allowed and family_access.reason_code == "EXTERNAL_SHARING_NOT_IMPLEMENTED"
    assert not family_access.external_share_performed
    assert receipt.local_development_only and not receipt.external_sharing_authorized
