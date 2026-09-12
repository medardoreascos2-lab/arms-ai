from fastapi import (
    Depends,
    FastAPI,
)
from fastapi.testclient import TestClient

from backend.api.admin_authorization_dependency_v2 import (
    ADMIN_TOKEN_HEADER,
    require_admin_authorization_v2,
)
from backend.security.admin_authorization_v2 import (
    AdminAuthorizationV2,
)


def build_client(
    *,
    authority,
) -> TestClient:
    app = FastAPI()

    app.state.admin_authorization_v2 = (
        authority
    )

    @app.post(
        "/protected",
        dependencies=[
            Depends(
                require_admin_authorization_v2
            )
        ],
    )
    def protected():
        return {
            "status": "AUTHORIZED"
        }

    return TestClient(app)


def test_admin_dependency_accepts_valid_token():
    client = build_client(
        authority=AdminAuthorizationV2(
            token="admin-secret",
        ),
    )

    response = client.post(
        "/protected",
        headers={
            ADMIN_TOKEN_HEADER:
                "admin-secret",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "AUTHORIZED"
    }


def test_admin_dependency_rejects_missing_token():
    client = build_client(
        authority=AdminAuthorizationV2(
            token="admin-secret",
        ),
    )

    response = client.post(
        "/protected"
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "admin_unauthorized"
    }


def test_admin_dependency_rejects_wrong_token():
    client = build_client(
        authority=AdminAuthorizationV2(
            token="admin-secret",
        ),
    )

    response = client.post(
        "/protected",
        headers={
            ADMIN_TOKEN_HEADER:
                "wrong-secret",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "admin_unauthorized"
    }


def test_admin_dependency_rejects_blank_token():
    client = build_client(
        authority=AdminAuthorizationV2(
            token="admin-secret",
        ),
    )

    response = client.post(
        "/protected",
        headers={
            ADMIN_TOKEN_HEADER: "   ",
        },
    )

    assert response.status_code == 401


def test_admin_dependency_fails_closed_without_authority():
    client = build_client(
        authority=None,
    )

    response = client.post(
        "/protected",
        headers={
            ADMIN_TOKEN_HEADER:
                "anything",
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail":
            "admin_authorization_not_configured"
    }


def test_admin_dependency_rejects_wrong_authority_type():
    client = build_client(
        authority=object(),
    )

    response = client.post(
        "/protected",
        headers={
            ADMIN_TOKEN_HEADER:
                "admin-secret",
        },
    )

    assert response.status_code == 503


def test_admin_header_name_is_independent_from_webhook_header():
    assert (
        ADMIN_TOKEN_HEADER
        == "X-ARMS-ADMIN-TOKEN"
    )

    assert (
        ADMIN_TOKEN_HEADER
        != "X-ARMS-TOKEN"
    )
