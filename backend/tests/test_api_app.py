from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_create_app_returns_fastapi_application():
    app = create_app()

    assert app.title == "ARMS AI API"
    assert app.version == "1.0.0"


def test_health_endpoint_returns_ok():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/health"
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "arms-ai-api",
    }


def test_openapi_schema_is_available():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/openapi.json"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["info"]["title"] == (
        "ARMS AI API"
    )
    assert "/health" in payload["paths"]
