"""Future ROSITA family-access policy; external sharing remains disabled."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.trusted_runtime_identity import (
    LocalAdminIdentityAuthority, RuntimeMemoryPermission, TrustedRuntimeIdentity,
)


class RositaAccessLevel(str, Enum):
    OWNER = "OWNER"
    FAMILY_AUTHORIZED = "FAMILY_AUTHORIZED"
    PRIVATE = "PRIVATE"
    RESTRICTED = "RESTRICTED"


@dataclass(frozen=True)
class RositaFamilyAccessPolicy:
    owner_id: str
    tenant_id: str
    access_level: RositaAccessLevel
    family_authorization_references: tuple[str, ...] = ()
    external_sharing_enabled: bool = False
    implementation_status: str = "POLICY_SEAM_ONLY"

    def __post_init__(self) -> None:
        for name in ("owner_id", "tenant_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be a bounded explicit reference")
        if not isinstance(self.access_level, RositaAccessLevel):
            raise TypeError("ROSITA access level must be explicit")
        if not isinstance(self.family_authorization_references, tuple) or len(self.family_authorization_references) > 20:
            raise ValueError("family authorization references must be bounded")
        for reference in self.family_authorization_references:
            if not isinstance(reference, str) or not reference.strip() or len(reference) > 240:
                raise ValueError("family authorization references must be bounded text")
        if self.access_level is RositaAccessLevel.FAMILY_AUTHORIZED:
            if not self.family_authorization_references:
                raise ValueError("family-authorized policy requires an authorization reference")
        elif self.family_authorization_references:
            raise ValueError("family references are valid only for family-authorized policy")
        if self.external_sharing_enabled or self.implementation_status != "POLICY_SEAM_ONLY":
            raise PermissionError("ROSITA external sharing is not implemented")


@dataclass(frozen=True)
class RositaAccessDecision:
    allowed: bool
    reason_code: str
    external_share_performed: bool = False

    def __post_init__(self) -> None:
        if self.external_share_performed:
            raise ValueError("ROSITA access decisions cannot perform external sharing")
        if self.allowed and self.reason_code != "LOCAL_OWNER_ALLOWED":
            raise ValueError("only authenticated local owner access can be allowed")


def evaluate_local_owner_access(
    authority: LocalAdminIdentityAuthority,
    identity: TrustedRuntimeIdentity,
    policy: RositaFamilyAccessPolicy,
) -> RositaAccessDecision:
    if not isinstance(authority, LocalAdminIdentityAuthority) or not isinstance(policy, RositaFamilyAccessPolicy):
        raise TypeError("trusted identity authority and ROSITA policy are required")
    try:
        authority.require_valid(identity)
    except PermissionError:
        return RositaAccessDecision(False, "IDENTITY_INVALID")
    if identity.owner_id != policy.owner_id or identity.tenant_id != policy.tenant_id:
        return RositaAccessDecision(False, "OWNER_SCOPE_MISMATCH")
    if RuntimeMemoryPermission.READ not in identity.permissions:
        return RositaAccessDecision(False, "READ_PERMISSION_MISSING")
    if policy.access_level is RositaAccessLevel.RESTRICTED:
        return RositaAccessDecision(False, "RESTRICTED_REVIEW_REQUIRED")
    return RositaAccessDecision(True, "LOCAL_OWNER_ALLOWED")


def evaluate_future_family_access(
    policy: RositaFamilyAccessPolicy,
    authorization_reference: str,
) -> RositaAccessDecision:
    if not isinstance(policy, RositaFamilyAccessPolicy):
        raise TypeError("ROSITA policy is required")
    if not isinstance(authorization_reference, str) or not authorization_reference.strip():
        return RositaAccessDecision(False, "FAMILY_AUTHORIZATION_MISSING")
    if policy.access_level is not RositaAccessLevel.FAMILY_AUTHORIZED:
        return RositaAccessDecision(False, "FAMILY_ACCESS_NOT_CONFIGURED")
    if authorization_reference not in policy.family_authorization_references:
        return RositaAccessDecision(False, "FAMILY_AUTHORIZATION_UNKNOWN")
    return RositaAccessDecision(False, "EXTERNAL_SHARING_NOT_IMPLEMENTED")
