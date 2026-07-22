from datetime import (
    datetime,
    timezone,
)

from fastapi.testclient import TestClient

from backend.api.app import create_app


def payload():
    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "open": 21600.0,
        "high": 21605.0,
        "low": 21598.0,
        "close": 21603.0,
        "volume": 1000.0,
        "timestamp": datetime(
            2026,
            7,
            22,
            19,
            30,
            tzinfo=timezone.utc,
        ).isoformat(),
    }


def test_rejects_missing_token():
    client = TestClient(create_app())

    response = client.post(
        "/market/webhook",
        json=payload(),
    )

    assert response.status_code == 401


def test_rejects_invalid_token():
    client = TestClient(create_app())

    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": "INVALID",
        },
        json=payload(),
    )

    assert response.status_code == 401
