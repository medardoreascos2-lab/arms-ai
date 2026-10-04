"""R121A integrates trusted memory retrieval with local-only model routing."""

from datetime import datetime, timezone
import sqlite3

import pytest

from backend.medar.deterministic_model import DeterministicModelProvider
from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.memory_access import MemoryPurpose
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.model_memory_runtime import MedarModelMemoryRuntime, ModelMemoryRuntimeRequest
from backend.medar.model_profiles import (
    CapabilityStrength, CostClass, LatencyClass, ModelCapabilityProfile,
    ModelLocality, ModelProfileRegistry,
)
from backend.medar.model_provider import ModelKind
from backend.medar.model_router import ModelRoutingRequirement, TaskComplexity
from backend.medar.request import CognitiveDomain
from backend.medar.runtime_model_router import RuntimeModelRouter
from backend.medar.sqlite_memory_store import MemoryScope, SQLiteMemoryStore
from backend.medar.trusted_runtime_identity import (
    LocalAdminIdentityAuthority, LocalIdentityAssignment, RuntimeMemoryPermission,
)
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


NOW = datetime(2026, 10, 4, 20, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def _profile():
    return ModelCapabilityProfile(
        "deterministic-test-model", ModelKind.LOCAL_LLM, 4096,
        CapabilityStrength.BASIC, CapabilityStrength.BASIC, LatencyClass.LOW,
        CostClass.FREE, ModelLocality.LOCAL, False, False, True,
    )


def _requirement():
    return ModelRoutingRequirement(
        CognitiveDomain.CODING, TaskComplexity.SIMPLE, 1024,
        CapabilityStrength.BASIC, local_only=True, remote_allowed=False,
        maximum_cost=CostClass.FREE,
    )


def _record():
    content = "Use schema checksums during recovery"
    return DurableMemoryRecord(
        "memory-1", SCOPE.owner_id, SCOPE.tenant_id, DurableMemoryDomain.TECHNICAL,
        DurableMemoryType.LESSON, content, content_digest(content), "synthetic_test", "source-1",
        MemoryProvenance("source-1", MemoryOrigin.OBSERVED, NOW, SCOPE.tenant_id, SCOPE.owner_id, "context-1", 0.9),
        ProvenanceClass.DIRECT_OBSERVATION, 0.9, 0.9, DurableSensitivity.PUBLIC,
        NOW, NOW, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )


def _runtime(path):
    authority = LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-token"),
        LocalIdentityAssignment(
            SCOPE.owner_id, SCOPE.tenant_id, "session-a", "medar-local",
            MemoryPurpose.TECHNICAL_ASSISTANCE,
            frozenset({RuntimeMemoryPermission.READ}),
        ),
        clock=lambda: NOW,
    )
    identity = authority.issue("synthetic-token")
    store = SQLiteMemoryStore(path)
    router = RuntimeModelRouter(ModelProfileRegistry((_profile(),)), (DeterministicModelProvider(),))
    return authority, identity, store, MedarModelMemoryRuntime(authority, store, router, clock=lambda: NOW)


def test_runtime_reads_cited_scope_and_invokes_only_validated_local_model(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False) as store:
        store.write(SCOPE, _record())
    before = path.read_bytes()
    authority, identity, store, runtime = _runtime(path)
    try:
        result = runtime.run(
            identity,
            ModelMemoryRuntimeRequest("request-1", "schema recovery", (DurableMemoryDomain.TECHNICAL,), DurableSensitivity.PUBLIC),
            _requirement(),
        )
    finally:
        store.close()

    assert len(result.memory_context.items) == 1
    assert result.memory_context.items[0].reference.memory_id == "memory-1"
    assert result.memory_context.items[0].reference.source_reference == "source-1"
    assert result.model_response.output.structured == {"answer": "test-value"}
    assert result.model_response.attempted_models == ("deterministic-test-model",)
    assert result.model_response.output.authorized_actions == ()
    assert not any((result.execution_authorized, result.broker_authorized, result.paper_authorized, result.live_authorized, result.persistence_performed, result.external_call_performed))
    assert path.read_bytes() == before


def test_runtime_denies_wrong_purpose_and_unissued_identity_before_model_call(tmp_path):
    path = tmp_path / "memory.db"
    with SQLiteMemoryStore(path, read_only=False):
        pass
    authority, identity, store, runtime = _runtime(path)
    try:
        with pytest.raises(PermissionError, match="purpose"):
            runtime.run(
                identity,
                ModelMemoryRuntimeRequest("request-2", "financial memory", (DurableMemoryDomain.FINANCIAL,), DurableSensitivity.PUBLIC),
                _requirement(),
            )
        foreign_authority, foreign_identity, foreign_store, _ = _runtime(path)
        try:
            with pytest.raises(PermissionError, match="issued"):
                runtime.run(
                    foreign_identity,
                    ModelMemoryRuntimeRequest("request-3", "schema", (DurableMemoryDomain.TECHNICAL,), DurableSensitivity.PUBLIC),
                    _requirement(),
                )
        finally:
            foreign_store.close()
    finally:
        store.close()
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM memory_versions").fetchone()[0] == 0
