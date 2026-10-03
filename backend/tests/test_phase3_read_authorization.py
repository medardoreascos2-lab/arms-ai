"""R32C tests for the pure tenant/account read authorization boundary."""

from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from backend.entitlements import FeatureEntitlement, UserIdentity, UserRole, UserStatus
from backend.phase3 import (
    AccountIdentity,
    AccountReadScope,
    AccountScopeMode,
    AuthorizationCode,
    AuthorizationPrincipal,
    ReadAction,
    ReadAuthorizationBoundary,
    ReadRequest,
)


ALL_FEATURES = frozenset(FeatureEntitlement)
BOUNDARY = ReadAuthorizationBoundary(frozenset({
    AccountIdentity("tenant-a", "account-1"),
    AccountIdentity("tenant-a", "account-2"),
    AccountIdentity("tenant-b", "account-9"),
}))


def principal(
    *,
    tenant_id="tenant-a",
    user_id="user-1",
    roles=frozenset({UserRole.OPERATOR}),
    entitlements=ALL_FEATURES,
    accounts=frozenset({"account-1"}),
    mode=AccountScopeMode.EXPLICIT,
    status=UserStatus.ACTIVE,
):
    return AuthorizationPrincipal(
        identity=UserIdentity(user_id, tenant_id, status=status),
        roles=roles,
        entitlements=entitlements,
        account_scope=AccountReadScope(tenant_id, mode, accounts),
    )


def request(action=ReadAction.ACCOUNT_STATE, **changes):
    values = dict(action=action, tenant_id="tenant-a", account_id="account-1")
    if action in (ReadAction.NOTIFICATION_EVENT, ReadAction.MEMBERSHIP_ENTITLEMENT):
        values.update(account_id=None, user_id="user-1")
    values.update(changes)
    return ReadRequest(**values)


def test_missing_authentication_denies_without_side_effect_authority():
    decision = BOUNDARY.evaluate(None, request())
    assert decision.allowed is False
    assert decision.code is AuthorizationCode.MISSING_AUTH
    assert decision.authorized_account_ids == ()
    assert decision.canonical_admin_authorized is False
    assert decision.execution_authorized is False
    assert decision.production_mutation_authorized is False


def test_tenant_a_cannot_read_tenant_b_and_denial_precedes_account_lookup():
    decision = BOUNDARY.evaluate(
        principal(),
        request(tenant_id="tenant-b", account_id="account-9"),
    )
    assert decision.code is AuthorizationCode.TENANT_MISMATCH
    assert decision.authorized_account_ids == ()


def test_unknown_and_out_of_scope_accounts_fail_closed():
    unknown = BOUNDARY.evaluate(principal(), request(account_id="account-missing"))
    denied = BOUNDARY.evaluate(principal(), request(account_id="account-2"))
    assert unknown.code is AuthorizationCode.ACCOUNT_UNKNOWN
    assert denied.code is AuthorizationCode.ACCOUNT_SCOPE_DENIED
    assert not unknown.allowed and not denied.allowed


def test_known_entitled_account_read_is_allowed_with_exact_scope_only():
    decision = BOUNDARY.evaluate(principal(), request())
    assert decision.allowed is True
    assert decision.code is AuthorizationCode.ALLOWED
    assert decision.authorized_account_ids == ("account-1",)
    assert decision.tenant_admin is False


def test_missing_permission_and_feature_entitlement_are_independent_denials():
    viewer = principal(roles=frozenset({UserRole.VIEWER}))
    assert BOUNDARY.evaluate(viewer, request()).code is AuthorizationCode.PERMISSION_MISSING

    no_policy = principal(
        entitlements=ALL_FEATURES - {FeatureEntitlement.PROP_FIRM_POLICY}
    )
    assert BOUNDARY.evaluate(no_policy, request()).code is (
        AuthorizationCode.ENTITLEMENT_MISSING
    )


def test_permissions_are_derived_and_cannot_be_injected_or_mutated():
    role_fields = {item.name for item in fields(AuthorizationPrincipal)}
    assert "permissions" in role_fields
    with pytest.raises(TypeError):
        AuthorizationPrincipal(
            identity=UserIdentity("user-1", "tenant-a"),
            roles=frozenset({UserRole.VIEWER}),
            entitlements=ALL_FEATURES,
            account_scope=AccountReadScope(
                "tenant-a", AccountScopeMode.EXPLICIT, frozenset()
            ),
            permissions=frozenset(),
        )
    with pytest.raises(FrozenInstanceError):
        principal().roles = frozenset({UserRole.TENANT_ADMIN})


def test_all_tenant_scope_requires_explicit_tenant_admin_role():
    with pytest.raises(ValueError, match="TENANT_ADMIN"):
        principal(mode=AccountScopeMode.ALL_TENANT_ACCOUNTS, accounts=frozenset())

    admin = principal(
        roles=frozenset({UserRole.TENANT_ADMIN}),
        mode=AccountScopeMode.ALL_TENANT_ACCOUNTS,
        accounts=frozenset(),
    )
    decision = BOUNDARY.evaluate(
        admin,
        request(ReadAction.PORTFOLIO_SUMMARY, account_id=None),
    )
    assert decision.allowed
    assert decision.tenant_admin is True
    assert decision.authorized_account_ids == ("account-1", "account-2")
    assert "account-9" not in decision.authorized_account_ids


def test_tenant_admin_never_bypasses_tenant_boundary():
    admin = principal(
        roles=frozenset({UserRole.TENANT_ADMIN}),
        mode=AccountScopeMode.ALL_TENANT_ACCOUNTS,
        accounts=frozenset(),
    )
    decision = BOUNDARY.evaluate(
        admin,
        request(tenant_id="tenant-b", account_id="account-9"),
    )
    assert decision.code is AuthorizationCode.TENANT_MISMATCH


def test_user_scoped_reads_allow_self_and_require_admin_for_other_user():
    self_read = BOUNDARY.evaluate(
        principal(roles=frozenset({UserRole.VIEWER})),
        request(ReadAction.MEMBERSHIP_ENTITLEMENT),
    )
    other_read = BOUNDARY.evaluate(
        principal(roles=frozenset({UserRole.VIEWER})),
        request(ReadAction.MEMBERSHIP_ENTITLEMENT, user_id="user-2"),
    )
    admin = principal(
        roles=frozenset({UserRole.TENANT_ADMIN}),
        mode=AccountScopeMode.ALL_TENANT_ACCOUNTS,
        accounts=frozenset(),
    )
    admin_read = BOUNDARY.evaluate(
        admin,
        request(ReadAction.MEMBERSHIP_ENTITLEMENT, user_id="user-2"),
    )
    assert self_read.allowed
    assert other_read.code is AuthorizationCode.USER_SCOPE_DENIED
    assert admin_read.allowed and admin_read.tenant_admin


def test_inactive_principal_is_denied_before_permissions():
    suspended = principal(status=UserStatus.SUSPENDED)
    decision = BOUNDARY.evaluate(suspended, request())
    assert decision.code is AuthorizationCode.PRINCIPAL_INACTIVE


def test_portfolio_scope_filters_known_accounts_and_denies_empty_scope():
    allowed = BOUNDARY.evaluate(
        principal(accounts=frozenset({"account-1", "unknown"})),
        request(ReadAction.PORTFOLIO_SUMMARY, account_id=None),
    )
    empty = BOUNDARY.evaluate(
        principal(accounts=frozenset({"unknown"})),
        request(ReadAction.PORTFOLIO_SUMMARY, account_id=None),
    )
    assert allowed.authorized_account_ids == ("account-1",)
    assert empty.code is AuthorizationCode.NO_ACCOUNTS_AUTHORIZED


def test_scope_and_boundary_inputs_are_immutable_and_validated():
    with pytest.raises(ValueError, match="immutable"):
        AccountReadScope("tenant-a", AccountScopeMode.EXPLICIT, {"account-1"})
    with pytest.raises(ValueError, match="match"):
        AuthorizationPrincipal(
            identity=UserIdentity("user-1", "tenant-a"),
            roles=frozenset({UserRole.OPERATOR}),
            entitlements=ALL_FEATURES,
            account_scope=AccountReadScope(
                "tenant-b", AccountScopeMode.EXPLICIT, frozenset()
            ),
        )
    with pytest.raises(ValueError, match="immutable"):
        ReadAuthorizationBoundary({AccountIdentity("tenant-a", "account-1")})


def test_requests_reject_irrelevant_scope_fields():
    with pytest.raises(ValueError, match="cannot carry user_id"):
        request(user_id="user-1")
    with pytest.raises(ValueError, match="cannot carry account_id"):
        request(ReadAction.MEMBERSHIP_ENTITLEMENT, account_id="account-1")


def test_authorization_module_has_no_io_network_or_execution_dependency():
    from backend.phase3 import read_authorization

    source = Path(read_authorization.__file__).read_text(encoding="utf-8")
    forbidden = (
        "sqlite3", "sqlalchemy", "backend.execution", "requests", "subprocess",
        "open(",
    )
    assert all(token not in source for token in forbidden)
