from backend.api.app import create_app
from backend.config.api_settings import APISettings
from backend.security.admin_authorization_v2 import (
    AdminAuthorizationV2,
)


def test_api_settings_admin_token_defaults_to_none(
    monkeypatch,
):
    monkeypatch.delenv(
        "ARMS_ADMIN_TOKEN",
        raising=False,
    )

    settings = APISettings()

    assert settings.admin_token is None


def test_api_settings_reads_admin_token_from_environment(
    monkeypatch,
):
    monkeypatch.setenv(
        "ARMS_ADMIN_TOKEN",
        "environment-admin-secret",
    )

    settings = APISettings()

    assert (
        settings.admin_token
        == "environment-admin-secret"
    )


def test_create_app_without_admin_token_has_no_admin_authority():
    settings = APISettings(
        admin_token=None,
    )

    app = create_app(
        settings=settings,
    )

    assert (
        app.state.admin_authorization_v2
        is None
    )


def test_create_app_constructs_independent_admin_authority():
    settings = APISettings(
        webhook_token="webhook-secret",
        admin_token="admin-secret",
    )

    app = create_app(
        settings=settings,
    )

    authority = (
        app.state
        .admin_authorization_v2
    )

    assert isinstance(
        authority,
        AdminAuthorizationV2,
    )

    assert authority.is_authorized(
        "admin-secret"
    ) is True

    assert authority.is_authorized(
        "webhook-secret"
    ) is False


def test_admin_and_webhook_credentials_remain_independent():
    settings = APISettings(
        webhook_token="market-data-secret",
        admin_token="operations-secret",
    )

    app = create_app(
        settings=settings,
    )

    assert (
        app.state.webhook_token
        == "market-data-secret"
    )

    assert (
        app.state.admin_authorization_v2
        .is_authorized(
            "operations-secret"
        )
        is True
    )

    assert (
        app.state.admin_authorization_v2
        .is_authorized(
            "market-data-secret"
        )
        is False
    )
