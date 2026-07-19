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


def test_value_error_is_returned_as_bad_request():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/rebalance",
        json={
            "current_weights": {
                "A": 100.0,
            },
            "target_weights": {
                "B": 100.0,
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "type": "ValueError",
            "message": (
                "current_weights y target_weights "
                "deben contener los mismos assets."
            ),
        }
    }


def test_domain_error_response_has_json_content_type():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/rebalance",
        json={
            "current_weights": {
                "A": 100.0,
            },
            "target_weights": {
                "B": 100.0,
            },
        },
    )

    assert response.headers[
        "content-type"
    ].startswith(
        "application/json"
    )
