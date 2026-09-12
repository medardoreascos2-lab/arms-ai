from fastapi.testclient import TestClient

from backend.api.admin_authorization_dependency_v2 import (
    ADMIN_TOKEN_HEADER,
    require_admin_authorization_v2,
)
from backend.api.app import create_app
from backend.config.api_settings import APISettings


PROTECTED_PATHS = {
    "/api/v3/dashboard/market-price",
    "/api/v2/market-hours/refresh",
}


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


def test_market_mutations_reject_missing_admin_token():
    _, client = build_client()

    probes = (
        (
            "/api/v3/dashboard/market-price",
            {},
        ),
        (
            "/api/v2/market-hours/refresh",
            {},
        ),
    )

    for path, payload in probes:
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


def test_market_mutations_reject_wrong_admin_token():
    _, client = build_client()

    for path in PROTECTED_PATHS:
        response = client.post(
            path,
            json={},
            headers={
                ADMIN_TOKEN_HEADER:
                    "wrong-secret",
            },
        )

        assert response.status_code == 401, (
            path,
            response.text,
        )


def test_market_mutations_fail_closed_when_unconfigured():
    _, client = build_client(
        admin_token=None,
    )

    for path in PROTECTED_PATHS:
        response = client.post(
            path,
            json={},
            headers={
                ADMIN_TOKEN_HEADER:
                    "anything",
            },
        )

        assert response.status_code == 503, (
            path,
            response.text,
        )


def test_valid_admin_token_reaches_market_request_validation():
    _, client = build_client()

    for path in PROTECTED_PATHS:
        response = client.post(
            path,
            json={},
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


def test_exact_market_mutations_have_admin_dependency():
    app, _ = build_client()

    found = set()

    for route in app.routes:
        path = getattr(
            route,
            "path",
            None,
        )

        if path not in PROTECTED_PATHS:
            continue

        deps = getattr(
            getattr(
                route,
                "dependant",
                None,
            ),
            "dependencies",
            [],
        )

        calls = {
            getattr(dep, "call", None)
            for dep in deps
        }

        assert (
            require_admin_authorization_v2
            in calls
        ), path

        found.add(path)

    assert found == PROTECTED_PATHS


def test_market_hours_reads_are_not_admin_protected():
    app, _ = build_client()

    read_paths = {
        "/api/v2/market-hours/status",
        "/api/v2/market-hours/coverage",
    }

    found = set()

    for route in app.routes:
        path = getattr(
            route,
            "path",
            None,
        )

        if path not in read_paths:
            continue

        deps = getattr(
            getattr(
                route,
                "dependant",
                None,
            ),
            "dependencies",
            [],
        )

        calls = {
            getattr(dep, "call", None)
            for dep in deps
        }

        assert (
            require_admin_authorization_v2
            not in calls
        ), path

        found.add(path)

    assert found == read_paths
