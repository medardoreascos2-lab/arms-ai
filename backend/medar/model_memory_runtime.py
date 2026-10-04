"""Trusted local MEDAR model and durable-memory runtime composition."""

from dataclasses import dataclass

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_access import (
    AuthorizedMemoryStore, MemoryAccessContext, MemoryAgentPermission, authorize_memory_access,
)
from backend.medar.memory_context_budget import MemoryContextBudget, select_memory_context
from backend.medar.memory_evidence_references import CitedMemoryContext, build_cited_memory_context
from backend.medar.memory_hybrid_retrieval import HybridMemoryRetriever
from backend.medar.memory_reranking import MemoryReranker
from backend.medar.model_provider import ModelInvocation, ModelKind
from backend.medar.model_router import ModelRoutingRequirement
from backend.medar.runtime_model_router import RuntimeModelResponse, RuntimeModelRouter
from backend.medar.sqlite_memory_store import MemoryStore
from backend.medar.trusted_runtime_identity import (
    LocalAdminIdentityAuthority, RuntimeMemoryPermission, TrustedRuntimeIdentity,
)


@dataclass(frozen=True)
class ModelMemoryRuntimeRequest:
    request_id: str
    query: str
    domains: tuple[DurableMemoryDomain, ...]
    sensitivity: DurableSensitivity
    maximum_context_tokens: int = 2048
    maximum_memories: int = 10

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ValueError("runtime request_id is required")
        if not isinstance(self.query, str) or not self.query.strip():
            raise ValueError("runtime query is required")
        if len(self.query) > 8192:
            raise ValueError("runtime query exceeds maximum length")
        if not isinstance(self.domains, tuple) or not self.domains or any(not isinstance(item, DurableMemoryDomain) for item in self.domains):
            raise ValueError("runtime domains must be a non-empty typed tuple")
        if len(set(self.domains)) != len(self.domains):
            raise ValueError("runtime domains must be unique")
        if not isinstance(self.sensitivity, DurableSensitivity):
            raise TypeError("runtime sensitivity must be typed")
        if isinstance(self.maximum_context_tokens, bool) or not isinstance(self.maximum_context_tokens, int) or not 1 <= self.maximum_context_tokens <= 32_768:
            raise ValueError("maximum_context_tokens must be 1 to 32768")
        if isinstance(self.maximum_memories, bool) or not isinstance(self.maximum_memories, int) or not 1 <= self.maximum_memories <= 100:
            raise ValueError("maximum_memories must be 1 to 100")


@dataclass(frozen=True)
class ModelMemoryRuntimeResult:
    request_id: str
    memory_context: CitedMemoryContext
    model_response: RuntimeModelResponse
    execution_authorized: bool = False
    broker_authorized: bool = False
    paper_authorized: bool = False
    live_authorized: bool = False
    persistence_performed: bool = False
    external_call_performed: bool = False

    def __post_init__(self) -> None:
        if any((
            self.execution_authorized, self.broker_authorized, self.paper_authorized,
            self.live_authorized, self.persistence_performed, self.external_call_performed,
        )):
            raise ValueError("model-memory runtime cannot grant authority or side effects")
        if self.memory_context.persistence_performed or self.memory_context.external_call_performed:
            raise ValueError("runtime memory context must be read-only and local")
        if self.model_response.external_call_performed:
            raise ValueError("runtime model response must be local")


class MedarModelMemoryRuntime:
    def __init__(
        self,
        authority: LocalAdminIdentityAuthority,
        store: MemoryStore,
        model_router: RuntimeModelRouter,
        *,
        clock=None,
    ) -> None:
        if not isinstance(authority, LocalAdminIdentityAuthority):
            raise TypeError("trusted identity authority is required")
        if not isinstance(model_router, RuntimeModelRouter):
            raise TypeError("runtime model router is required")
        self._authority = authority
        self._store = AuthorizedMemoryStore(store)
        self._router = model_router
        self._clock = clock

    def run(
        self,
        identity: TrustedRuntimeIdentity,
        request: ModelMemoryRuntimeRequest,
        requirement: ModelRoutingRequirement,
    ) -> ModelMemoryRuntimeResult:
        self._authority.require_valid(identity)
        if RuntimeMemoryPermission.READ not in identity.permissions:
            raise PermissionError("runtime identity lacks memory read permission")
        if not isinstance(request, ModelMemoryRuntimeRequest):
            raise TypeError("typed model-memory request is required")
        if not isinstance(requirement, ModelRoutingRequirement):
            raise TypeError("typed model routing requirement is required")
        contexts = tuple(
            MemoryAccessContext(
                requester_id=identity.owner_id,
                requester_tenant_id=identity.tenant_id,
                owner_id=identity.owner_id,
                tenant_id=identity.tenant_id,
                domain=domain,
                sensitivity=request.sensitivity,
                purpose=identity.purpose,
                permission=MemoryAgentPermission.READ,
            )
            for domain in request.domains
        )
        for context in contexts:
            authorize_memory_access(context, "read")
        hybrid = HybridMemoryRetriever(self._store, clock=self._clock).retrieve(
            contexts, request.query, limit=request.maximum_memories,
        )
        reranked = MemoryReranker(self._store, clock=self._clock).rerank(
            contexts, request.query, hybrid, limit=request.maximum_memories,
        )
        per_domain = max(1, request.maximum_context_tokens // len(request.domains))
        selection = select_memory_context(
            reranked,
            MemoryContextBudget(
                request.maximum_context_tokens,
                request.maximum_memories,
                {domain: per_domain for domain in request.domains},
                frozenset({request.sensitivity}),
            ),
        )
        cited = build_cited_memory_context(selection, self._store, contexts)
        evidence_lines = tuple(
            f"[{item.reference.memory_id}@{item.reference.version}|{item.reference.source_reference}] {item.content}"
            for item in cited.items
        )
        prompt = "\n".join((
            "Answer the request using only the authorized cited memory when relevant.",
            f"REQUEST: {request.query}",
            "CITED_MEMORY:",
            *(evidence_lines or ("NONE",)),
        ))
        kind = requirement.required_kind or ModelKind.LOCAL_LLM
        if kind is ModelKind.REMOTE_LLM:
            raise PermissionError("remote model invocation is disabled")
        invocation = ModelInvocation(
            request.request_id + ":model", "runtime-selected", kind, prompt,
            {"answer": "string"},
        )
        response = self._router.invoke(requirement, invocation)
        return ModelMemoryRuntimeResult(request.request_id, cited, response)
