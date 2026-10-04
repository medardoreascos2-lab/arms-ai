"""R121C validates the cited technical outcome-to-lesson learning loop."""

from datetime import datetime, timezone
import json

from backend.medar.bound_memory_access import BoundMemoryRequest
from backend.medar.durable_memory_encryption import AESGCMEphemeralMemoryEncryption
from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity, RetentionPolicy
from backend.medar.encrypted_memory_envelope import open_memory_content
from backend.medar.learned_lesson_memory import LearnedLessonMemory, LearnedLessonWriteAuthority
from backend.medar.lesson_extraction import LessonDraft, extract_lesson
from backend.medar.memory_access import MemoryPurpose
from backend.medar.outcome_evaluator import OutcomeEvidence, OutcomeClassification, evaluate_outcome
from backend.medar.outcome_event import OutcomeEvent
from backend.medar.sqlite_encrypted_memory_store import SQLiteEncryptedMemoryStore
from backend.medar.sqlite_memory_store import MemoryScope
from backend.medar.trusted_runtime_identity import LocalAdminIdentityAuthority, LocalIdentityAssignment, RuntimeMemoryPermission
from backend.security.admin_authorization_v2 import AdminAuthorizationV2

NOW = datetime(2026, 10, 4, 21, tzinfo=timezone.utc)


def test_technical_outcome_becomes_cited_encrypted_lesson_without_model_or_execution_authority(tmp_path):
    event = OutcomeEvent(
        "outcome-technical-1", "tenant-a", "owner-a", "session-a", "synthetic-test:technical-run-1",
        "validate schema migration", "run bounded validation", "migration remains intact",
        "all checks pass", "all checks pass", "pytest evidence", None, NOW,
    )
    evaluation = evaluate_outcome(
        event,
        OutcomeEvidence(event.event_id, ("synthetic-test:pytest-technical-1",), True, 1.0, False),
        evaluated_at=NOW,
    )
    assert evaluation.classification is OutcomeClassification.SUCCESS
    lesson = extract_lesson(
        event, evaluation,
        LessonDraft("schema validation caught drift", "no observed failure", "synthetic local test", "repeat schema validation"),
        lesson_id="lesson-technical-1", extracted_at=NOW,
    )
    memory = LearnedLessonMemory("tenant-a", "owner-a", "session-a", event.source_reference, lesson, NOW)
    authority = LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-token"),
        LocalIdentityAssignment("owner-a", "tenant-a", "session-a", "medar-local", MemoryPurpose.TECHNICAL_ASSISTANCE, frozenset({RuntimeMemoryPermission.READ, RuntimeMemoryPermission.WRITE})),
        clock=lambda: NOW,
    )
    identity = authority.issue("synthetic-token")
    request = BoundMemoryRequest("owner-a", "tenant-a", "session-a", "medar-local", DurableMemoryDomain.SEMANTIC, DurableSensitivity.SENSITIVE, MemoryPurpose.TECHNICAL_ASSISTANCE)
    path = tmp_path / "technical-lessons.db"
    with AESGCMEphemeralMemoryEncryption(local_development_enabled=True) as crypto:
        writer = LearnedLessonWriteAuthority(authority, crypto, local_development_enabled=True)
        approval = writer.approve(identity, request, memory, RetentionPolicy.LONG_TERM)
        with SQLiteEncryptedMemoryStore(path, read_only=False) as store:
            receipt = writer.persist(identity, request, memory, RetentionPolicy.LONG_TERM, approval, store)
        with SQLiteEncryptedMemoryStore(path) as store:
            envelope = store.get(MemoryScope("tenant-a", "owner-a"), lesson.lesson_id, 1)
        plaintext = open_memory_content(envelope, crypto, memory_id=lesson.lesson_id, owner_id="owner-a", tenant_id="tenant-a", domain=DurableMemoryDomain.SEMANTIC, sensitivity=DurableSensitivity.SENSITIVE, version=1)

    document = json.loads(plaintext)
    assert document["outcome_event_id"] == event.event_id
    assert document["evidence_references"] == ["synthetic-test:pytest-technical-1"]
    assert document["future_recommendation"] == "repeat schema validation"
    assert memory.lesson.what_worked.encode() not in path.read_bytes()
    assert not receipt.execution_authority and not receipt.model_update_authority
    assert not lesson.hidden_chain_of_thought_included and not lesson.learning_authority
