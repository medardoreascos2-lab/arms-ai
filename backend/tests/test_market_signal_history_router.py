from datetime import (
    datetime,
    timedelta,
    timezone,
)

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.services.signal_history_store import (
    SignalHistoryStore,
)


def build_signal(
    index: int,
) -> dict[str, object]:
    generated_at = (
        datetime(
            2026,
            7,
            22,
            9,
            30,
            tzinfo=timezone.utc,
        )
        + timedelta(
            minutes=index * 5
        )
    )

    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "current_price": 21691.0 + index,
        "action": (
            "BUY"
            if index % 2 == 0
            else "WAIT"
        ),
        "approved": index % 2 == 0,
        "score": 88.0 - index,
        "grade": "A+",
        "probability": 84.0,
        "confidence": "MUY ALTA",
        "risk_approved": True,
        "entry_price": 21691.0 + index,
        "stop_loss": 21672.25 + index,
        "take_profit": 21728.50 + index,
        "reason": "Señal de prueba.",
        "generated_at": generated_at,
    }


def test_market_signal_history_endpoint():
    store = SignalHistoryStore()

    for index in range(3):
        store.append(
            build_signal(index)
        )

    client = TestClient(
        create_app(
            signal_history_store=store
        )
    )

    response = client.get(
        "/market/signals",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
            "limit": 10,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["symbol"] == "NQ"
    assert body["timeframe"] == "5m"
    assert body["count"] == 3
    assert len(body["signals"]) == 3
    assert body["signals"][0]["entry_price"] == 21691.0
    assert body["signals"][-1]["entry_price"] == 21693.0


def test_market_signal_history_respects_limit():
    store = SignalHistoryStore()

    for index in range(5):
        store.append(
            build_signal(index)
        )

    client = TestClient(
        create_app(
            signal_history_store=store
        )
    )

    response = client.get(
        "/market/signals",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
            "limit": 2,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["count"] == 2
    assert body["signals"][0]["entry_price"] == 21694.0
    assert body["signals"][1]["entry_price"] == 21695.0


def test_market_signal_history_returns_empty_list():
    store = SignalHistoryStore()

    client = TestClient(
        create_app(
            signal_history_store=store
        )
    )

    response = client.get(
        "/market/signals",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
            "limit": 10,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["count"] == 0
    assert body["signals"] == []


def test_market_signal_history_rejects_invalid_limit():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/signals",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
            "limit": 0,
        },
    )

    assert response.status_code == 422


def test_market_signal_history_requires_symbol():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/signals",
        params={
            "timeframe": "5m",
            "limit": 10,
        },
    )

    assert response.status_code == 422
