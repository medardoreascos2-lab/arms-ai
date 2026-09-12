from fastapi.testclient import TestClient

from backend.api.admin_authorization_dependency_v2 import (
    ADMIN_TOKEN_HEADER,
)
from backend.api.app import create_app
from backend.config.api_settings import APISettings


PROTECTED = (
    (
        "/api/v2/dashboard/account-manager/switch",
        {
            "account_id": "__invalid_probe__",
            "profile_name": "__invalid_probe__",
        },
    ),
    (
        "/api/v2/dashboard/account/switch",
        {
            "account_id": "__invalid_probe__",
            "profile_name": "__invalid_probe__",
        },
    ),
    (
        "/v2/trades/submit",
        {},
    ),
    (
        "/v2/positions/missing/update",
        {},
    ),
)


def build_client(
    *,
    admin_token="admin-secret",
):
    app = create_app(
        settings=APISettings(
            admin_token=admin_token,
        )
    )

    return app, TestClient(app)


def test_protected_operations_reject_missing_admin_token():
    _, client = build_client()

    for path, payload in PROTECTED:
        response = client.post(
            path,
            json=payload,
        )

        assert response.status_code == 401, (
            path,
            response.text,
        )

        assert response.json() == {
            "detail": "admin_unauthorized"
        }


def test_protected_operations_reject_wrong_admin_token():
    _, client = build_client()

    for path, payload in PROTECTED:
        response = client.post(
            path,
            json=payload,
            headers={
                ADMIN_TOKEN_HEADER:
                    "wrong-secret",
            },
        )

        assert response.status_code == 401, (
            path,
            response.text,
        )


def test_protected_operations_fail_closed_when_unconfigured():
    _, client = build_client(
        admin_token=None,
    )

    for path, payload in PROTECTED:
        response = client.post(
            path,
            json=payload,
            headers={
                ADMIN_TOKEN_HEADER:
                    "anything",
            },
        )

        assert response.status_code == 503, (
            path,
            response.text,
        )


def test_valid_admin_token_reaches_request_validation():
    _, client = build_client()

    for path, payload in PROTECTED:
        response = client.post(
            path,
            json=payload,
            headers={
                ADMIN_TOKEN_HEADER:
                    "admin-secret",
            },
        )

        assert response.status_code not in {
            401,
            503,
        }, (
            path,
            response.text,
        )


def test_exact_four_routes_have_admin_dependency():
    app, _ = build_client()

    expected = {
        "/api/v2/dashboard/account-manager/switch",
        "/api/v2/dashboard/account/switch",
        "/v2/trades/submit",
        "/v2/positions/{position_id}/update",
    }

    actual = set()

    for route in app.routes:
        path = getattr(
            route,
            "path",
            None,
        )

        if path not in expected:
            continue

        dependant = getattr(
            route,
            "dependant",
            None,
        )

        dependencies = (
            getattr(
                dependant,
                "dependencies",
                [],
            )
            if dependant is not None
            else []
        )

        calls = {
            getattr(
                dependency,
                "call",
                None,
            )
            for dependency in dependencies
        }

        from backend.api.admin_authorization_dependency_v2 import (
            require_admin_authorization_v2,
        )

        assert (
            require_admin_authorization_v2
            in calls
        ), path

        actual.add(path)

    assert actual == expected
