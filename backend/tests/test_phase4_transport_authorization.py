"""R45B tests for deny-by-default Phase 4 transport authorization."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.entitlements import FeatureEntitlement, UserIdentity, UserRole, UserStatus
from backend.phase3.read_authorization import (
    AccountReadScope,
    AccountScopeMode,
    AuthorizationPrincipal,
)
from backend.phase3.state_contracts import AccountIdentity
from backend.phase4.secret_providers import SecretReference
from backend.phase4.service_identity import (
    ServiceCredentialRotation,
    ServiceIdentity,
    ServicePermission,
    ServiceTenantScope,
)
from backend.phase4.transport_authorization import (
    TRANSPORT_REQUIREMENTS,
    AuthenticatedServiceTransportPrincipal,
    AuthenticatedUserTransportPrincipal,
    Phase4TransportAction,
    Phase4TransportAuthorizationBoundary,
    Phase4TransportRequest,
    TransportAuthorizationCode,
)


NOW = datetime(2026, 10, 4, 3, 0, tzinfo=timezone.utc)
KNOWN = frozenset({
    AccountIdentity("tenant-a", "account-1"),
    AccountIdentity("tenant-a", "account-2"),
})


def user(*, role=UserRole.OPERATOR, status=UserStatus.ACTIVE):
    principal = AuthorizationPrincipal(
        identity=UserIdentity("user-1", "tenant-a", status=status),
        roles=frozenset({role}),
        entitlements=frozenset(FeatureEntitlement),
        account_scope=AccountReadScope(
            "tenant-a", AccountScopeMode.EXPLICIT, frozenset({"account-1"})
        ),
    )
    return AuthenticatedUserTransportPrincipal(principal, "tenant-a", NOW)


def service(*, permissions=frozenset({ServicePermission.OPERATIONS_READ})):
    identity = ServiceIdentity(
        "phase4.operations-reader",
        ServiceTenantScope(frozenset({"tenant-a"})),
        permissions,
        SecretReference("service/operations/v1"),
        NOW + timedelta(hours=2),
        ServiceCredentialRotation(1, NOW - timedelta(hours=1), NOW + timedelta(hours=1)),
    )
    return AuthenticatedServiceTransportPrincipal(
        identity,
        "tenant-a",
        AccountReadScope(
            "tenant-a", AccountScopeMode.EXPLICIT, frozenset({"account-1"})
        ),
        NOW,
    )


def decision(principal, action, account_id=None, at=NOW):
    return Phase4TransportAuthorizationBoundary(KNOWN).evaluate(
        principal,
        Phase4TransportRequest(action, "tenant-a", account_id),
        evaluated_at=at,
    )


def test_authenticated_user_and_service_are_authorized_with_required_scope():
    user_result = decision(user(), Phase4TransportAction.ACCOUNT_OPERATIONS_READ, "account-1")
    service_result = decision(service(), Phase4TransportAction.ACCOUNT_OPERATIONS_READ, "account-1")
    assert user_result.code is TransportAuthorizationCode.ALLOWED
    assert service_result.code is TransportAuthorizationCode.ALLOWED
    assert user_result.execution_authorized is False
    assert service_result.production_mutation_authorized is False


def test_missing_or_unknown_principal_is_denied_by_default():
    assert decision(None, Phase4TransportAction.HEALTH_READ).code is TransportAuthorizationCode.MISSING_AUTH
    assert decision(object(), Phase4TransportAction.HEALTH_READ).code is TransportAuthorizationCode.MISSING_AUTH


def test_tenant_claim_and_account_scope_cannot_cross_boundaries():
    boundary = Phase4TransportAuthorizationBoundary(KNOWN)
    tenant_mismatch = boundary.evaluate(
        user(),
        Phase4TransportRequest(Phase4TransportAction.HEALTH_READ, "tenant-b"),
        evaluated_at=NOW,
    )
    denied_account = decision(
        user(), Phase4TransportAction.ACCOUNT_OPERATIONS_READ, "account-2"
    )
    unknown_account = decision(
        user(), Phase4TransportAction.ACCOUNT_OPERATIONS_READ, "account-unknown"
    )
    assert tenant_mismatch.code is TransportAuthorizationCode.TENANT_MISMATCH
    assert denied_account.code is TransportAuthorizationCode.ACCOUNT_SCOPE_DENIED
    assert unknown_account.code is TransportAuthorizationCode.ACCOUNT_UNKNOWN


def test_user_and_service_permissions_are_enforced_independently():
    viewer = user(role=UserRole.VIEWER)
    missing_service_permission = service(
        permissions=frozenset({ServicePermission.HEALTH_READ})
    )
    assert decision(
        viewer, Phase4TransportAction.METRICS_READ
    ).code is TransportAuthorizationCode.PERMISSION_MISSING
    assert decision(
        missing_service_permission, Phase4TransportAction.OPERATIONS_READ
    ).code is TransportAuthorizationCode.PERMISSION_MISSING


def test_inactive_user_expired_service_and_future_authentication_are_denied():
    assert decision(
        user(status=UserStatus.SUSPENDED), Phase4TransportAction.HEALTH_READ
    ).code is TransportAuthorizationCode.PRINCIPAL_INACTIVE
    assert decision(
        service(), Phase4TransportAction.OPERATIONS_READ, at=NOW + timedelta(hours=2)
    ).code is TransportAuthorizationCode.CREDENTIAL_EXPIRED
    future_user = AuthenticatedUserTransportPrincipal(user().principal, "tenant-a", NOW + timedelta(seconds=1))
    assert decision(
        future_user, Phase4TransportAction.HEALTH_READ
    ).code is TransportAuthorizationCode.AUTH_TIME_INVALID


def test_request_shape_enforces_account_scope_contract():
    with pytest.raises(ValueError, match="requires account_id"):
        Phase4TransportRequest(Phase4TransportAction.ACCOUNT_OPERATIONS_READ, "tenant-a")
    with pytest.raises(ValueError, match="cannot carry"):
        Phase4TransportRequest(Phase4TransportAction.HEALTH_READ, "tenant-a", "account-1")


def test_requirements_are_immutable_and_actions_are_read_only():
    with pytest.raises(TypeError):
        TRANSPORT_REQUIREMENTS[Phase4TransportAction.HEALTH_READ] = None
    assert all(action.value.endswith("_READ") for action in Phase4TransportAction)


def test_transport_boundary_has_no_execution_or_production_authority():
    boundary = Phase4TransportAuthorizationBoundary(KNOWN)
    assert boundary.execution_authorized is False
    assert boundary.production_mutation_authorized is False
