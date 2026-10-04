"""Authenticated user forget request seam without false deletion claims."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from backend.medar.memory_candidates import has_secret_like_content
from backend.medar.trusted_runtime_identity import LocalAdminIdentityAuthority, TrustedRuntimeIdentity


class ForgetRequestStatus(str, Enum):
    REQUIRES_STORAGE_REVIEW = "REQUIRES_STORAGE_REVIEW"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class MemoryForgetRequest:
    request_id: str
    tenant_id: str
    owner_id: str
    memory_ids: tuple[str, ...]
    reason: str = field(repr=False)
    requested_at: datetime
    deletion_authority: bool = False
    deletion_completed: bool = False

    def __post_init__(self) -> None:
        for name in ("request_id", "tenant_id", "owner_id", "reason"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 512:
                raise ValueError(f"{name} must be bounded non-empty text")
            if has_secret_like_content(value):
                raise PermissionError("secret-like forget request content is not retained")
        if not self.memory_ids or len(self.memory_ids) > 100:
            raise ValueError("forget request must identify bounded memory IDs")
        if len(set(self.memory_ids)) != len(self.memory_ids) or any(
            not isinstance(value, str) or not value.strip() or len(value) > 240
            for value in self.memory_ids
        ):
            raise ValueError("forget request memory IDs must be unique bounded text")
        if not isinstance(self.requested_at, datetime) or self.requested_at.tzinfo is None or self.requested_at.utcoffset() is None:
            raise ValueError("forget request time must be timezone-aware")
        if self.deletion_authority or self.deletion_completed:
            raise ValueError("forget request cannot claim deletion authority or completion")


@dataclass(frozen=True)
class MemoryForgetReceipt:
    request_id: str
    status: ForgetRequestStatus
    pending_storage_layers: tuple[str, ...]
    deleted_memory_ids: tuple[str, ...] = ()
    asynchronous_deletion_complete: bool = False

    def __post_init__(self) -> None:
        if self.status is not ForgetRequestStatus.REQUIRES_STORAGE_REVIEW:
            raise ValueError("accepted forget request must require storage review")
        if not self.pending_storage_layers:
            raise ValueError("forget receipt must retain pending storage layers")
        if self.deleted_memory_ids or self.asynchronous_deletion_complete:
            raise ValueError("forget seam cannot claim deletion completion")


def submit_memory_forget_request(
    authority: LocalAdminIdentityAuthority,
    identity: TrustedRuntimeIdentity,
    request: MemoryForgetRequest,
    *,
    known_storage_layers: tuple[str, ...],
) -> MemoryForgetReceipt:
    if not isinstance(authority, LocalAdminIdentityAuthority):
        raise TypeError("trusted identity authority is required")
    authority.require_valid(identity)
    if not isinstance(request, MemoryForgetRequest):
        raise TypeError("memory forget request is required")
    if identity.tenant_id != request.tenant_id or identity.owner_id != request.owner_id:
        raise PermissionError("forget request scope does not match trusted identity")
    if not isinstance(known_storage_layers, tuple) or not known_storage_layers:
        raise ValueError("known storage layers must be enumerated")
    if len(set(known_storage_layers)) != len(known_storage_layers) or any(
        not isinstance(layer, str) or not layer.strip() or len(layer) > 120
        for layer in known_storage_layers
    ):
        raise ValueError("known storage layers must be unique bounded names")
    return MemoryForgetReceipt(
        request.request_id, ForgetRequestStatus.REQUIRES_STORAGE_REVIEW,
        tuple(sorted(known_storage_layers)),
    )
