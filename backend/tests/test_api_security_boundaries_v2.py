from fastapi.testclient import TestClient

from backend.api.admin_authorization_dependency_v2 import (
    ADMIN_TOKEN_HEADER,
    require_admin_authorization_v2,
)
from backend.api.app import create_app
from backend.config.api_settings import APISettings


ADMIN_TOKEN = "admin-secret"


PROTECTED_MUTATIONS = (
    (
        "account administration",
        "/api/v2/dashboard/account-manager/switch",
        "POST",
        {
            "account_id": "__invalid_probe__",
            "profile_name": "__invalid_probe__",
        },
    ),
    (
        "account switching alias",
        "/api/v2/dashboard/account/switch",
        "POST",
        {
            "account_id": "__invalid_probe__",
            "profile_name": "__invalid_probe__",
        },
    ),
    (
        "trade submission",
        "/v2/trades/submit",
        "POST",
        {},
    ),
    (
        "position update",
        "/v2/positions/__missing_probe__/update",
        "POST",
        {},
    ),
    (
        "backtesting controller start",
        "/api/v2/backtesting/controller/start",
        "POST",
        {},
    ),
    (
        "backtesting job creation",
        "/api/v2/backtesting/jobs",
        "POST",
        {},
    ),
    (
        "backtesting queue processing",
        "/api/v2/backtesting/jobs/process-next",
        "POST",
        {},
    ),
    (
        "backtesting job deletion",
        "/api/v2/backtesting/jobs/__missing_probe__",
        "DELETE",
        None,
    ),
    (
        "market price update",
        "/api/v3/dashboard/market-price",
        "POST",
        {},
    ),
    (
        "market hours refresh",
        "/api/v2/market-hours/refresh",
        "POST",
        {},
    ),
)


READ_ONLY_ROUTES = (
    (
        "health",
        "/health",
    ),
    (
        "account manager",
        "/api/v2/dashboard/account-manager",
    ),
    (
        "available accounts",
        "/api/v2/dashboard/account-manager/available",
    ),
    (
        "account switch context",
        "/api/v2/dashboard/account-manager/switch-context",
    ),
    (
        "market hours status",
        "/api/v2/market-hours/status",
    ),
    (
        "market hours coverage",
        "/api/v2/market-hours/coverage",
    ),
    (
        "backtesting controller status",
        "/api/v2/backtesting/controller/status",
    ),
    (
        "backtesting jobs",
        "/api/v2/backtesting/jobs",
    ),
)


def build_client(
    *,
    admin_token: str | None = ADMIN_TOKEN,
) -> tuple[object, TestClient]:
    app = create_app(
        settings=APISettings(
            admin_token=admin_token,
        )
    )

    return app, TestClient(app)


def request_mutation(
    client: TestClient,
    *,
    path: str,
    method: str,
    payload: dict | None,
    headers: dict[str, str] | None = None,
):
    request_kwargs = {
        "headers": headers or {},
    }

    if method == "DELETE":
        return client.delete(
            path,
            **request_kwargs,
        )

    return client.request(
        method,
        path,
        json=payload or {},
        **request_kwargs,
    )


def test_protected_mutations_reject_missing_authorization():
    _, client = build_client()

    for (
        operation,
        path,
        method,
        payload,
    ) in PROTECTED_MUTATIONS:
        response = request_mutation(
            client,
            path=path,
            method=method,
            payload=payload,
        )

        assert response.status_code == 401, (
            operation,
            path,
            response.status_code,
            response.text,
        )

        assert response.json() == {
            "detail": "admin_unauthorized",
        }


def test_protected_mutations_reject_invalid_authorization():
    _, client = build_client()

    for (
        operation,
        path,
        method,
        payload,
    ) in PROTECTED_MUTATIONS:
        response = request_mutation(
            client,
            path=path,
            method=method,
            payload=payload,
            headers={
                ADMIN_TOKEN_HEADER: "wrong-secret",
            },
        )

        assert response.status_code == 401, (
            operation,
            path,
            response.status_code,
            response.text,
        )

        assert response.json() == {
            "detail": "admin_unauthorized",
        }


def test_correct_authorization_reaches_protected_handlers():
    _, client = build_client()

    for (
        operation,
        path,
        method,
        payload,
    ) in PROTECTED_MUTATIONS:
        response = request_mutation(
            client,
            path=path,
            method=method,
            payload=payload,
            headers={
                ADMIN_TOKEN_HEADER: ADMIN_TOKEN,
            },
        )

        assert response.status_code != 401, (
            operation,
            path,
            response.status_code,
            response.text,
        )


def test_unconfigured_authorization_fails_closed_for_protected_mutations():
    _, client = build_client(
        admin_token=None,
    )

    for (
        operation,
        path,
        method,
        payload,
    ) in PROTECTED_MUTATIONS:
        response = request_mutation(
            client,
            path=path,
            method=method,
            payload=payload,
            headers={
                ADMIN_TOKEN_HEADER: "anything",
            },
        )

        assert response.status_code == 503, (
            operation,
            path,
            response.status_code,
            response.text,
        )

        assert response.json() == {
            "detail": "admin_authorization_not_configured",
        }


def test_read_only_routes_remain_available_without_admin_authorization():
    _, client = build_client()

    for operation, path in READ_ONLY_ROUTES:
        response = client.get(path)

        assert response.status_code not in {
            401,
            503,
        }, (
            operation,
            path,
            response.status_code,
            response.text,
        )


def test_protected_aliases_are_not_authorization_bypasses():
    _, client = build_client()

    account_switch_paths = {
        "/api/v2/dashboard/account-manager/switch",
        "/api/v2/dashboard/account/switch",
    }

    for path in account_switch_paths:
        response = client.post(
            path,
            json={
                "account_id": "__invalid_probe__",
                "profile_name": "__invalid_probe__",
            },
        )

        assert response.status_code == 401, (
            path,
            response.status_code,
            response.text,
        )

        assert response.json() == {
            "detail": "admin_unauthorized",
        }


def test_expected_protected_routes_use_admin_authorization_dependency():
    app, _ = build_client()

    expected_routes = {
        (
            "/api/v2/dashboard/account-manager/switch",
            "POST",
        ),
        (
            "/api/v2/dashboard/account/switch",
            "POST",
        ),
        (
            "/v2/trades/submit",
            "POST",
        ),
        (
            "/v2/positions/{position_id}/update",
            "POST",
        ),
        (
            "/api/v2/backtesting/controller/start",
            "POST",
        ),
        (
            "/api/v2/backtesting/jobs",
            "POST",
        ),
        (
            "/api/v2/backtesting/jobs/process-next",
            "POST",
        ),
        (
            "/api/v2/backtesting/jobs/{job_id}",
            "DELETE",
        ),
        (
            "/api/v3/dashboard/market-price",
            "POST",
        ),
        (
            "/api/v2/market-hours/refresh",
            "POST",
        ),
    }

    found_routes = set()

    for route in app.routes:
        route_path = getattr(
            route,
            "path",
            None,
        )

        route_methods = set(
            getattr(
                route,
                "methods",
                set(),
            )
            or set()
        )

        for expected_path, expected_method in expected_routes:
            if (
                route_path != expected_path
                or expected_method not in route_methods
            ):
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

            dependency_calls = {
                getattr(
                    dependency,
                    "call",
                    None,
                )
                for dependency in dependencies
            }

            assert (
                require_admin_authorization_v2
                in dependency_calls
            ), (
                expected_path,
                expected_method,
            )

            found_routes.add(
                (
                    expected_path,
                    expected_method,
                )
            )

    assert found_routes == expected_routes


def test_expected_read_only_routes_do_not_use_admin_authorization_dependency():
    app, _ = build_client()

    expected_routes = {
        (
            "/api/v2/dashboard/account-manager",
            "GET",
        ),
        (
            "/api/v2/dashboard/account-manager/available",
            "GET",
        ),
        (
            "/api/v2/dashboard/account-manager/switch-context",
            "GET",
        ),
        (
            "/api/v2/market-hours/status",
            "GET",
        ),
        (
            "/api/v2/market-hours/coverage",
            "GET",
        ),
        (
            "/api/v2/backtesting/controller/status",
            "GET",
        ),
        (
            "/api/v2/backtesting/jobs",
            "GET",
        ),
    }

    found_routes = set()

    for route in app.routes:
        route_path = getattr(
            route,
            "path",
            None,
        )

        route_methods = set(
            getattr(
                route,
                "methods",
                set(),
            )
            or set()
        )

        for expected_path, expected_method in expected_routes:
            if (
                route_path != expected_path
                or expected_method not in route_methods
            ):
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

            dependency_calls = {
                getattr(
                    dependency,
                    "call",
                    None,
                )
                for dependency in dependencies
            }

            assert (
                require_admin_authorization_v2
                not in dependency_calls
            ), (
                expected_path,
                expected_method,
            )

            found_routes.add(
                (
                    expected_path,
                    expected_method,
                )
            )

    assert found_routes == expected_routes
