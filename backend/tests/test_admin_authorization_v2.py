import pytest

from backend.security.admin_authorization_v2 import (
    AdminAuthorizationV2,
)


def test_admin_authorization_accepts_exact_token():
    authority = AdminAuthorizationV2(
        token="admin-secret",
    )

    assert authority.is_authorized(
        "admin-secret"
    ) is True


def test_admin_authorization_rejects_wrong_token():
    authority = AdminAuthorizationV2(
        token="admin-secret",
    )

    assert authority.is_authorized(
        "wrong-secret"
    ) is False


def test_admin_authorization_rejects_missing_token():
    authority = AdminAuthorizationV2(
        token="admin-secret",
    )

    assert authority.is_authorized(
        None
    ) is False


def test_admin_authorization_rejects_blank_token():
    authority = AdminAuthorizationV2(
        token="admin-secret",
    )

    assert authority.is_authorized(
        "   "
    ) is False


def test_admin_authorization_rejects_empty_configured_token():
    with pytest.raises(
        ValueError,
        match="admin token must not be empty",
    ):
        AdminAuthorizationV2(
            token="   ",
        )


def test_admin_authorization_rejects_non_string_configured_token():
    with pytest.raises(
        TypeError,
        match="token must be a string",
    ):
        AdminAuthorizationV2(
            token=None,  # type: ignore[arg-type]
        )


def test_require_authorized_accepts_valid_token():
    authority = AdminAuthorizationV2(
        token="admin-secret",
    )

    authority.require_authorized(
        "admin-secret"
    )


def test_require_authorized_fails_closed():
    authority = AdminAuthorizationV2(
        token="admin-secret",
    )

    with pytest.raises(
        PermissionError,
        match="admin_unauthorized",
    ):
        authority.require_authorized(
            "wrong-secret"
        )
