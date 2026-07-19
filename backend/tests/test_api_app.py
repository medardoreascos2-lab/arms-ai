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


def test_type_error_is_returned_as_bad_request():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/optimize",
        json={
            "returns": {
                "A": [1, 2, 3],
            },
            "volatilities": {
                "A": 0.10,
            },
            "expected_returns": {
                "A": 0.08,
            },
        },
    )

    assert response.status_code == 200


def test_type_error_handler_returns_json():
    from backend.api.app import create_app

    app = create_app()

    handlers = app.exception_handlers

    assert TypeError in handlers


def test_validation_error_uses_standard_format():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/simulate",
        json={},
    )

    assert response.status_code == 422

    payload = response.json()

    assert payload["error"]["type"] == (
        "RequestValidationError"
    )


def test_validation_error_contains_message():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/simulate",
        json={},
    )

    payload = response.json()

    assert isinstance(
        payload["error"]["message"],
        str,
    )
    assert payload["error"]["message"]
