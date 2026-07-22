from datetime import (
    datetime,
    timezone,
)

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.services.live_candle_store import (
    LiveCandleStore,
)


def build_payload() -> dict[str, object]:
    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "open": 21600.0,
        "high": 21605.0,
        "low": 21598.0,
        "close": 21603.0,
        "volume": 1250.0,
        "timestamp": datetime(
            2026,
            7,
            22,
            9,
            30,
            tzinfo=timezone.utc,
        ).isoformat(),
    }


def test_market_webhook_stores_candle():
    store = LiveCandleStore(
        max_candles=500
    )

    client = TestClient(
        create_app(
            live_candle_store=store
        )
    )

    response = client.post(
        "/market/webhook",
        json=build_payload(),
    )

    assert response.status_code == 201

    body = response.json()

    assert body["status"] == "stored"
    assert body["symbol"] == "NQ"
    assert body["timeframe"] == "5m"
    assert body["count"] == 1

    candles = store.get_latest(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(candles) == 1
    assert candles[0].close == 21603.0


def test_market_webhook_replaces_same_timestamp():
    store = LiveCandleStore()

    client = TestClient(
        create_app(
            live_candle_store=store
        )
    )

    first = build_payload()

    second = {
        **build_payload(),
        "close": 21604.5,
        "volume": 1400.0,
    }

    first_response = client.post(
        "/market/webhook",
        json=first,
    )

    second_response = client.post(
        "/market/webhook",
        json=second,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json()["count"] == 1

    candles = store.get_latest(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(candles) == 1
    assert candles[0].close == 21604.5
    assert candles[0].volume == 1400.0


def test_market_webhook_rejects_invalid_ohlc():
    store = LiveCandleStore()

    client = TestClient(
        create_app(
            live_candle_store=store
        )
    )

    payload = build_payload()
    payload["high"] = 21590.0

    response = client.post(
        "/market/webhook",
        json=payload,
    )

    assert response.status_code == 422


def test_market_webhook_rejects_negative_volume():
    store = LiveCandleStore()

    client = TestClient(
        create_app(
            live_candle_store=store
        )
    )

    payload = build_payload()
    payload["volume"] = -1

    response = client.post(
        "/market/webhook",
        json=payload,
    )

    assert response.status_code == 422
