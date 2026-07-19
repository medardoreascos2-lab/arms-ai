import logging

from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_request_is_logged(caplog):
    app = create_app()

    client = TestClient(app)

    with caplog.at_level(
        logging.INFO,
        logger="arms-ai",
    ):
        response = client.get(
            "/health"
        )

    assert response.status_code == 200

    assert any(
        "GET /health" in record.message
        for record in caplog.records
    )


def test_status_code_is_logged(caplog):
    app = create_app()

    client = TestClient(app)

    with caplog.at_level(
        logging.INFO,
        logger="arms-ai",
    ):
        client.get("/health")

    assert any(
        "200" in record.message
        for record in caplog.records
    )


def test_execution_time_is_logged(caplog):
    app = create_app()

    client = TestClient(app)

    with caplog.at_level(
        logging.INFO,
        logger="arms-ai",
    ):
        client.get("/health")

    assert any(
        "ms" in record.message
        for record in caplog.records
    )
