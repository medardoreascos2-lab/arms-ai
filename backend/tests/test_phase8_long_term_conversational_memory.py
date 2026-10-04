"""R121B validates long-term conversational memory across a store restart."""

from datetime import datetime, timezone

from backend.medar.deterministic_model import DeterministicModelProvider
from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType, DurableSensitivity,
    MemoryLifecycle, ProvenanceClass, RetentionPolicy, content_digest,
)
from backend.medar.memory_access import MemoryPurpose
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.model_memory_runtime import MedarModelMemoryRuntime, ModelMemoryRuntimeRequest
from backend.medar.model_profiles import CapabilityStrength, CostClass, LatencyClass, ModelCapabilityProfile, ModelLocality, ModelProfileRegistry
from backend.medar.model_provider import ModelKind
from backend.medar.model_router import ModelRoutingRequirement, TaskComplexity
from backend.medar.request import CognitiveDomain
from backend.medar.runtime_model_router import RuntimeModelRouter
from backend.medar.sqlite_memory_store import MemoryScope, SQLiteMemoryStore
from backend.medar.trusted_runtime_identity import LocalAdminIdentityAuthority, LocalIdentityAssignment, RuntimeMemoryPermission
from backend.security.admin_authorization_v2 import AdminAuthorizationV2

NOW = datetime(2026, 10, 4, 20, 30, tzinfo=timezone.utc)
SCOPE = MemoryScope("tenant-a", "owner-a")


def test_authorized_conversational_preference_survives_restart_and_is_cited(tmp_path):
    path = tmp_path / "conversation-memory.db"
    content = "User explicitly prefers concise technical explanations"
    record = DurableMemoryRecord(
        "preference-1", SCOPE.owner_id, SCOPE.tenant_id, DurableMemoryDomain.PREFERENCES,
        DurableMemoryType.PREFERENCE, content, content_digest(content), "user_statement", "conversation-1",
        MemoryProvenance("conversation-1", MemoryOrigin.OBSERVED, NOW, SCOPE.tenant_id, SCOPE.owner_id, "session-before-restart", 1.0),
        ProvenanceClass.USER_STATED, 1.0, 0.8, DurableSensitivity.INTERNAL,
        NOW, NOW, None, RetentionPolicy.LONG_TERM, MemoryLifecycle.ACTIVE, 1,
    )
    with SQLiteMemoryStore(path, read_only=False) as store:
        store.write(SCOPE, record)

    authority = LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-token"),
        LocalIdentityAssignment(SCOPE.owner_id, SCOPE.tenant_id, "session-after-restart", "medar-local", MemoryPurpose.PERSONALIZATION, frozenset({RuntimeMemoryPermission.READ})),
        clock=lambda: NOW,
    )
    identity = authority.issue("synthetic-token")
    profile = ModelCapabilityProfile("deterministic-test-model", ModelKind.LOCAL_LLM, 4096, CapabilityStrength.BASIC, CapabilityStrength.BASIC, LatencyClass.LOW, CostClass.FREE, ModelLocality.LOCAL, False, False, True)
    router = RuntimeModelRouter(ModelProfileRegistry((profile,)), (DeterministicModelProvider(),))
    requirement = ModelRoutingRequirement(CognitiveDomain.GENERAL, TaskComplexity.SIMPLE, 1024, CapabilityStrength.BASIC, local_only=True, maximum_cost=CostClass.FREE)
    before = path.read_bytes()
    with SQLiteMemoryStore(path) as reopened:
        result = MedarModelMemoryRuntime(authority, reopened, router, clock=lambda: NOW).run(
            identity,
            ModelMemoryRuntimeRequest("conversation-2", "concise technical explanations", (DurableMemoryDomain.PREFERENCES,), DurableSensitivity.INTERNAL),
            requirement,
        )

    assert [item.reference.memory_id for item in result.memory_context.items] == ["preference-1"]
    assert result.memory_context.items[0].content == content
    assert result.memory_context.items[0].reference.provenance.context_id == "session-before-restart"
    assert result.model_response.output.structured == {"answer": "test-value"}
    assert path.read_bytes() == before
    assert not result.persistence_performed and not result.external_call_performed
