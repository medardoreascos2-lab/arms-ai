"""R113C ROSITA family-access seam keeps all external sharing disabled."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.medar.memory_access import MemoryPurpose
from backend.medar.rosita_access_policy import (
    RositaAccessLevel, RositaFamilyAccessPolicy, evaluate_future_family_access,
    evaluate_local_owner_access,
)
from backend.medar.trusted_runtime_identity import (
    LocalAdminIdentityAuthority, LocalIdentityAssignment, RuntimeMemoryPermission,
)
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def _identity():
    authority = LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-test-token"),
        LocalIdentityAssignment(
            "owner-a", "tenant-a", "session-a", "medar-local",
            MemoryPurpose.RESEARCH,
            frozenset({RuntimeMemoryPermission.READ, RuntimeMemoryPermission.WRITE}),
        ), clock=lambda: NOW,
    )
    return authority, authority.issue("synthetic-test-token")


@pytest.mark.parametrize("level", tuple(RositaAccessLevel))
def test_policy_represents_each_access_level_without_enabling_external_sharing(level):
    references = ("synthetic-test:family-approval-1",) if level is RositaAccessLevel.FAMILY_AUTHORIZED else ()
    policy = RositaFamilyAccessPolicy("owner-a", "tenant-a", level, references)
    assert policy.access_level is level
    assert not policy.external_sharing_enabled
    assert policy.implementation_status == "POLICY_SEAM_ONLY"


def test_authenticated_local_owner_access_is_allowed_except_restricted_review():
    authority, identity = _identity()
    for level in (RositaAccessLevel.OWNER, RositaAccessLevel.PRIVATE, RositaAccessLevel.FAMILY_AUTHORIZED):
        references = ("synthetic-test:family-approval-1",) if level is RositaAccessLevel.FAMILY_AUTHORIZED else ()
        decision = evaluate_local_owner_access(
            authority, identity,
            RositaFamilyAccessPolicy("owner-a", "tenant-a", level, references),
        )
        assert decision.allowed and not decision.external_share_performed
    restricted = evaluate_local_owner_access(
        authority, identity,
        RositaFamilyAccessPolicy("owner-a", "tenant-a", RositaAccessLevel.RESTRICTED),
    )
    assert not restricted.allowed
    assert restricted.reason_code == "RESTRICTED_REVIEW_REQUIRED"


def test_spoofed_owner_or_tenant_is_denied():
    authority, identity = _identity()
    policy = RositaFamilyAccessPolicy("owner-a", "tenant-a", RositaAccessLevel.OWNER)
    for changed in (replace(identity, owner_id="other"), replace(identity, tenant_id="other")):
        decision = evaluate_local_owner_access(authority, changed, policy)
        assert not decision.allowed
        assert not decision.external_share_performed


def test_family_authorization_is_recorded_but_never_grants_external_access():
    policy = RositaFamilyAccessPolicy(
        "owner-a", "tenant-a", RositaAccessLevel.FAMILY_AUTHORIZED,
        ("synthetic-test:family-approval-1",),
    )
    missing = evaluate_future_family_access(policy, "")
    unknown = evaluate_future_family_access(policy, "synthetic-test:other")
    known = evaluate_future_family_access(policy, "synthetic-test:family-approval-1")
    assert not missing.allowed and missing.reason_code == "FAMILY_AUTHORIZATION_MISSING"
    assert not unknown.allowed and unknown.reason_code == "FAMILY_AUTHORIZATION_UNKNOWN"
    assert not known.allowed and known.reason_code == "EXTERNAL_SHARING_NOT_IMPLEMENTED"
    assert not any(item.external_share_performed for item in (missing, unknown, known))


def test_policy_rejects_external_sharing_and_misplaced_family_references():
    with pytest.raises(PermissionError):
        RositaFamilyAccessPolicy(
            "owner-a", "tenant-a", RositaAccessLevel.OWNER,
            external_sharing_enabled=True,
        )
    with pytest.raises(ValueError):
        RositaFamilyAccessPolicy("owner-a", "tenant-a", RositaAccessLevel.FAMILY_AUTHORIZED)
    with pytest.raises(ValueError):
        RositaFamilyAccessPolicy(
            "owner-a", "tenant-a", RositaAccessLevel.PRIVATE,
            ("synthetic-test:family-approval-1",),
        )
