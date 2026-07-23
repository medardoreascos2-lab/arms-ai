from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.services.live_signal_store import (
    LiveSignalStore,
)


def build_signal() -> dict[str, object]:
    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "current_price": 21691.0,
        "action": "BUY",
        "approved": True,
        "score": 88.0,
        "grade": "A+",
        "probability": 84.0,
        "confidence": "MUY ALTA",
        "risk_approved": True,
        "entry_price": 21691.0,
        "stop_loss": 21672.25,
        "take_profit": 21728.50,
        "reason": (
            "Señal aprobada por decisión, "
            "probabilidad y gestión de riesgo."
        ),
    }


def test_latest_market_signal_endpoint():
    store = LiveSignalStore()

    store.save(
        build_signal()
    )

    client = TestClient(
        create_app(
            live_signal_store=store
        )
    )

    response = client.get(
        "/market/latest-signal",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["symbol"] == "NQ"
    assert body["timeframe"] == "5m"
    assert body["action"] == "BUY"
    assert body["approved"] is True
    assert body["score"] == 88.0
    assert body["probability"] == 84.0


def test_latest_market_signal_returns_404_when_missing():
    store = LiveSignalStore()

    client = TestClient(
        create_app(
            live_signal_store=store
        )
    )

    response = client.get(
        "/market/latest-signal",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
        },
    )

    assert response.status_code == 404


def test_latest_market_signal_requires_symbol():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/latest-signal",
        params={
            "timeframe": "5m",
        },
    )

    assert response.status_code == 422


def test_latest_market_signal_requires_timeframe():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/latest-signal",
        params={
            "symbol": "NQ",
        },
    )

    assert response.status_code == 422
