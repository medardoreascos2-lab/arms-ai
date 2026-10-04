"""Memory reads bound to an authority-issued runtime identity.

No API integration or durable write authority is implied by this facade.
"""

from dataclasses import dataclass

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableMemoryRecord, DurableSensitivity
from backend.medar.memory_access import (
    AuthorizedMemoryStore, MemoryAccessContext, MemoryAgentPermission,
    MemoryPurpose, authorize_memory_access,
)
from backend.medar.sqlite_memory_store import MemoryStore
from backend.medar.trusted_runtime_identity import (
    LocalAdminIdentityAuthority, RuntimeMemoryPermission, TrustedRuntimeIdentity,
)


@dataclass(frozen=True)
class BoundMemoryRequest:
    owner_id: str
    tenant_id: str
    session_id: str
    service_id: str | None
    domain: DurableMemoryDomain
    sensitivity: DurableSensitivity
    purpose: MemoryPurpose
    claimed_permission: RuntimeMemoryPermission | None = None
    claimed_role: str | None = None

    def __post_init__(self) -> None:
        for name in ("owner_id", "tenant_id", "session_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if self.service_id is not None and (not isinstance(self.service_id, str) or not self.service_id.strip()):
            raise ValueError("service_id must be non-empty when provided")
        if not isinstance(self.domain, DurableMemoryDomain) or not isinstance(self.sensitivity, DurableSensitivity):
            raise TypeError("domain and sensitivity must be typed")
        if not isinstance(self.purpose, MemoryPurpose):
            raise TypeError("purpose must be typed")
        if self.claimed_permission is not None and not isinstance(self.claimed_permission, RuntimeMemoryPermission):
            raise TypeError("claimed_permission must be typed")
        if self.claimed_role is not None and (not isinstance(self.claimed_role, str) or not self.claimed_role.strip()):
            raise ValueError("claimed_role must be non-empty when provided")


class BoundMemoryAccess:
    def __init__(self, authority: LocalAdminIdentityAuthority, store: MemoryStore):
        if not isinstance(authority, LocalAdminIdentityAuthority):
            raise TypeError("trusted identity authority is required")
        self._authority = authority
        self._facade = AuthorizedMemoryStore(store)

    def _bind(
        self,
        identity: TrustedRuntimeIdentity,
        request: BoundMemoryRequest,
        operation: RuntimeMemoryPermission,
    ) -> MemoryAccessContext:
        self._authority.require_valid(identity)
        if not isinstance(request, BoundMemoryRequest):
            raise TypeError("bound memory request is required")
        if (
            request.owner_id != identity.owner_id
            or request.tenant_id != identity.tenant_id
            or request.session_id != identity.session_id
            or request.service_id != identity.service_id
            or request.purpose is not identity.purpose
        ):
            raise PermissionError("memory request does not match trusted runtime identity")
        if request.claimed_role is not None:
            raise PermissionError("caller role cannot grant memory authority")
        if request.claimed_permission is not None and request.claimed_permission is not operation:
            raise PermissionError("caller permission cannot override runtime identity")
        if operation not in identity.permissions:
            raise PermissionError("runtime identity lacks memory permission")
        context = MemoryAccessContext(
            requester_id=identity.owner_id,
            requester_tenant_id=identity.tenant_id,
            owner_id=identity.owner_id,
            tenant_id=identity.tenant_id,
            domain=request.domain,
            sensitivity=request.sensitivity,
            purpose=identity.purpose,
            permission=MemoryAgentPermission.READ if operation is RuntimeMemoryPermission.READ else MemoryAgentPermission.WRITE,
            persistence_approved=False,
        )
        authorize_memory_access(context, "read" if operation is RuntimeMemoryPermission.READ else "write")
        return context

    def get(self, identity: TrustedRuntimeIdentity, request: BoundMemoryRequest, memory_id: str) -> DurableMemoryRecord | None:
        context = self._bind(identity, request, RuntimeMemoryPermission.READ)
        return self._facade.get(context, memory_id)

    def search(self, identity: TrustedRuntimeIdentity, request: BoundMemoryRequest, query: str, limit: int = 10) -> tuple[DurableMemoryRecord, ...]:
        context = self._bind(identity, request, RuntimeMemoryPermission.READ)
        return self._facade.search(context, query, limit)

    def list_active(self, identity: TrustedRuntimeIdentity, request: BoundMemoryRequest, max_records: int = 10_000) -> tuple[DurableMemoryRecord, ...]:
        context = self._bind(identity, request, RuntimeMemoryPermission.READ)
        return self._facade.list_active(context, max_records)
