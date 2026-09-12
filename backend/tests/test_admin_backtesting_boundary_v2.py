from fastapi.testclient import TestClient

from backend.api.admin_authorization_dependency_v2 import (
    ADMIN_TOKEN_HEADER,
    require_admin_authorization_v2,
)
from backend.api.app import create_app
from backend.config.api_settings import APISettings


PROTECTED = {
    (
        "/api/v2/backtesting/controller/start",
        "POST",
    ),
    (
        "/api/v2/backtesting/controller/stop",
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
}


READ_ONLY = {
    (
        "/api/v2/backtesting/controller/status",
        "GET",
    ),
    (
        "/api/v2/backtesting/jobs",
        "GET",
    ),
    (
        "/api/v2/backtesting/jobs/{job_id}",
        "GET",
    ),
    (
        "/api/v2/backtesting/jobs/{job_id}/result",
        "GET",
    ),
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


def request_without_token(
    client,
    *,
    path,
    method,
):
    if method == "DELETE":
        return client.delete(path)

    return client.post(
        path,
        json={},
    )


def request_with_token(
    client,
    *,
    path,
    method,
    token,
):
    headers = {
        ADMIN_TOKEN_HEADER: token,
    }

    if method == "DELETE":
        return client.delete(
            path,
            headers=headers,
        )

    return client.post(
        path,
        json={},
        headers=headers,
    )


def concrete_path(
    path: str,
) -> str:
    return path.replace(
        "{job_id}",
        "__missing_probe__",
    )


def test_backtesting_mutations_reject_missing_admin_token():
    _, client = build_client()

    for path, method in PROTECTED:
        response = request_without_token(
            client,
            path=concrete_path(path),
            method=method,
        )

        assert response.status_code == 401, (
            path,
            response.text,
        )

        assert response.json() == {
            "detail": "admin_unauthorized"
        }


def test_backtesting_mutations_reject_wrong_admin_token():
    _, client = build_client()

    for path, method in PROTECTED:
        response = request_with_token(
            client,
            path=concrete_path(path),
            method=method,
            token="wrong-secret",
        )

        assert response.status_code == 401, (
            path,
            response.text,
        )


def test_backtesting_mutations_fail_closed_when_unconfigured():
    _, client = build_client(
        admin_token=None,
    )

    for path, method in PROTECTED:
        response = request_with_token(
            client,
            path=concrete_path(path),
            method=method,
            token="anything",
        )

        assert response.status_code == 503, (
            path,
            response.text,
        )


def test_valid_admin_token_reaches_handler_or_validation():
    _, client = build_client()

    for path, method in PROTECTED:
        response = request_with_token(
            client,
            path=concrete_path(path),
            method=method,
            token="admin-secret",
        )

        assert response.status_code != 401, (
            path,
            response.text,
        )


def test_exact_backtesting_mutations_are_admin_protected():
    app, _ = build_client()

    found = set()

    for route in app.routes:
        path = getattr(
            route,
            "path",
            None,
        )

        methods = set(
            getattr(
                route,
                "methods",
                set(),
            )
            or set()
        )

        for expected_path, expected_method in PROTECTED:
            if (
                path == expected_path
                and expected_method in methods
            ):
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
                    getattr(
                        dep,
                        "call",
                        None,
                    )
                    for dep in deps
                }

                assert (
                    require_admin_authorization_v2
                    in calls
                ), (
                    expected_path,
                    expected_method,
                )

                found.add(
                    (
                        expected_path,
                        expected_method,
                    )
                )

    assert found == PROTECTED


def test_backtesting_reads_are_not_admin_protected():
    app, _ = build_client()

    found = set()

    for route in app.routes:
        path = getattr(
            route,
            "path",
            None,
        )

        methods = set(
            getattr(
                route,
                "methods",
                set(),
            )
            or set()
        )

        for expected_path, expected_method in READ_ONLY:
            if (
                path == expected_path
                and expected_method in methods
            ):
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
                    getattr(
                        dep,
                        "call",
                        None,
                    )
                    for dep in deps
                }

                assert (
                    require_admin_authorization_v2
                    not in calls
                ), (
                    expected_path,
                    expected_method,
                )

                found.add(
                    (
                        expected_path,
                        expected_method,
                    )
                )

    assert found == READ_ONLY
