"""R114D validated lessons are encrypted separately from raw outcomes."""

import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.medar.bound_memory_access import BoundMemoryRequest
from backend.medar.durable_memory_encryption import AESGCMEphemeralMemoryEncryption
from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity, RetentionPolicy
from backend.medar.encrypted_memory_envelope import open_memory_content
from backend.medar.learned_lesson_memory import LearnedLessonMemory, LearnedLessonWriteAuthority
from backend.medar.lesson_extraction import LessonDraft, extract_lesson
from backend.medar.memory_access import MemoryPurpose
from backend.medar.outcome_evaluator import OutcomeEvidence, evaluate_outcome
from backend.medar.outcome_event import OutcomeEvent
from backend.medar.sqlite_encrypted_memory_store import SQLiteEncryptedMemoryStore
from backend.medar.sqlite_memory_store import MemoryScope
from backend.medar.trusted_runtime_identity import (
    LocalAdminIdentityAuthority, LocalIdentityAssignment, RuntimeMemoryPermission,
)
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


NOW = datetime(2026, 10, 4, 14, tzinfo=timezone.utc)


class SpyStore:
    def __init__(self):
        self.calls = []

    def write(self, scope, envelope):
        self.calls.append((scope, envelope))


def _setup():
    identity_authority = LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-test-token"),
        LocalIdentityAssignment(
            "owner-a", "tenant-a", "session-a", "medar-local",
            MemoryPurpose.TECHNICAL_ASSISTANCE,
            frozenset({RuntimeMemoryPermission.READ, RuntimeMemoryPermission.WRITE}),
        ),
        clock=lambda: NOW,
    )
    identity = identity_authority.issue("synthetic-test-token")
    event = OutcomeEvent(
        "outcome-1", "tenant-a", "owner-a", "session-a",
        "synthetic-test:outcome-1", "raw task detail", "raw decision detail",
        "raw prediction detail", "raw expected detail", "raw observed detail",
        "raw success metric", None, NOW,
    )
    evaluation = evaluate_outcome(
        event,
        OutcomeEvidence("outcome-1", ("synthetic-test:evidence-1",), True, 1.0, False),
        evaluated_at=NOW,
    )
    lesson = extract_lesson(
        event, evaluation,
        LessonDraft("bounded validation worked", "no failure", "synthetic run", "repeat validation"),
        lesson_id="lesson-1", extracted_at=NOW,
    )
    memory = LearnedLessonMemory(
        "tenant-a", "owner-a", "session-a", "synthetic-test:outcome-1", lesson, NOW,
    )
    request = BoundMemoryRequest(
        "owner-a", "tenant-a", "session-a", "medar-local",
        DurableMemoryDomain.SEMANTIC, DurableSensitivity.SENSITIVE,
        MemoryPurpose.TECHNICAL_ASSISTANCE,
    )
    return identity_authority, identity, event, memory, request


def test_validated_lesson_is_encrypted_separately_without_raw_outcome(tmp_path):
    identity_authority, identity, event, memory, request = _setup()
    path = tmp_path / "learned-lessons.db"
    with AESGCMEphemeralMemoryEncryption(local_development_enabled=True) as provider:
        authority = LearnedLessonWriteAuthority(
            identity_authority, provider, local_development_enabled=True,
        )
        approval = authority.approve(identity, request, memory, RetentionPolicy.LONG_TERM)
        with SQLiteEncryptedMemoryStore(path, read_only=False) as store:
            receipt = authority.persist(
                identity, request, memory, RetentionPolicy.LONG_TERM, approval, store,
            )
        assert receipt.memory_id == "lesson-1"
        assert receipt.outcome_event_id == "outcome-1"
        assert receipt.memory_id != receipt.outcome_event_id
        assert not receipt.execution_authority and not receipt.model_update_authority
        with SQLiteEncryptedMemoryStore(path) as store:
            envelope = store.get(MemoryScope("tenant-a", "owner-a"), "lesson-1", 1)
        assert envelope is not None
        content = open_memory_content(
            envelope, provider, memory_id="lesson-1", owner_id="owner-a",
            tenant_id="tenant-a", domain=DurableMemoryDomain.SEMANTIC,
            sensitivity=DurableSensitivity.SENSITIVE, version=1,
        )
        document = json.loads(content)
        assert document["what_worked"] == "bounded validation worked"
        assert document["outcome_event_id"] == event.event_id
        for raw_value in (
            event.task, event.decision, event.prediction, event.expected_result,
            event.observed_result, event.success_metric,
        ):
            assert raw_value not in content
        database_bytes = path.read_bytes()
        assert memory.lesson.what_worked.encode() not in database_bytes
        assert event.task.encode() not in database_bytes


def test_scope_approval_and_retention_denials_have_zero_store_writes():
    identity_authority, identity, _event, memory, request = _setup()
    with AESGCMEphemeralMemoryEncryption(local_development_enabled=True) as provider:
        authority = LearnedLessonWriteAuthority(
            identity_authority, provider, local_development_enabled=True,
        )
        approval = authority.approve(identity, request, memory, RetentionPolicy.LONG_TERM)
        spy = SpyStore()
        for denied_request in (
            replace(request, owner_id="other"),
            replace(request, tenant_id="other"),
            replace(request, session_id="other"),
            replace(request, domain=DurableMemoryDomain.EPISODIC),
            replace(request, sensitivity=DurableSensitivity.INTERNAL),
        ):
            with pytest.raises(PermissionError):
                authority.persist(
                    identity, denied_request, memory, RetentionPolicy.LONG_TERM, approval, spy,
                )
        with pytest.raises(PermissionError):
            authority.persist(
                identity, request, memory, RetentionPolicy.SESSION, approval, spy,
            )
        assert spy.calls == []


def test_stale_or_changed_lesson_approval_has_zero_store_writes():
    identity_authority, identity, _event, memory, request = _setup()
    with AESGCMEphemeralMemoryEncryption(local_development_enabled=True) as provider:
        authority = LearnedLessonWriteAuthority(
            identity_authority, provider, local_development_enabled=True,
        )
        approval = authority.approve(identity, request, memory, RetentionPolicy.LONG_TERM)
        changed_lesson = replace(memory.lesson, future_recommendation="different recommendation")
        changed_memory = replace(memory, lesson=changed_lesson)
        spy = SpyStore()
        with pytest.raises(PermissionError):
            authority.persist(
                identity, request, changed_memory, RetentionPolicy.LONG_TERM, approval, spy,
            )
        assert spy.calls == []


def test_unmarked_source_and_missing_local_crypto_are_rejected():
    identity_authority, identity, _event, memory, request = _setup()
    with AESGCMEphemeralMemoryEncryption(local_development_enabled=True) as provider:
        authority = LearnedLessonWriteAuthority(
            identity_authority, provider, local_development_enabled=True,
        )
        with pytest.raises(PermissionError):
            authority.approve(
                identity, request, replace(memory, source_reference="outcome-1"),
                RetentionPolicy.LONG_TERM,
            )
    with AESGCMEphemeralMemoryEncryption(local_development_enabled=True) as provider:
        with pytest.raises(PermissionError):
            LearnedLessonWriteAuthority(identity_authority, provider)


def test_lesson_cannot_be_rewrapped_under_another_owner_or_source():
    _identity_authority, _identity, _event, memory, _request = _setup()
    with pytest.raises(PermissionError):
        replace(memory, owner_id="other")
    with pytest.raises(PermissionError):
        replace(memory, source_reference="synthetic-test:other")
