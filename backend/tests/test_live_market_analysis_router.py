from datetime import (
    datetime,
    timedelta,
    timezone,
)

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.models.candle import Candle
from backend.services.live_candle_store import (
    LiveCandleStore,
)


def populate_store(
    store: LiveCandleStore,
    total: int = 60,
) -> None:
    start = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone.utc,
    )

    for index in range(total):
        base = 21600.0 + index * 1.5

        store.add(
            Candle(
                symbol="NQ",
                timeframe="5m",
                open=base,
                high=base + 4.0,
                low=base - 2.0,
                close=base + 2.5,
                volume=1000.0 + index * 10,
                timestamp=(
                    start
                    + timedelta(
                        minutes=index * 5
                    )
                ),
            )
        )


def build_payload() -> dict[str, object]:
    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "candle_limit": 60,
        "account_balance": 17000.0,
        "risk_percent": 0.5,
        "point_value": 2.0,
        "reward_risk_ratio": 2.0,
    }


def test_live_market_analysis_endpoint():
    store = LiveCandleStore()
    populate_store(store)

    client = TestClient(
        create_app(
            live_candle_store=store
        )
    )

    response = client.post(
        "/market/analyze",
        json=build_payload(),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["symbol"] == "NQ"
    assert body["timeframe"] == "5m"
    assert body["current_price"] == 21691.0

    assert "trend" in body
    assert "indicators" in body
    assert "market_structure" in body
    assert "smart_money" in body
    assert "decision" in body
    assert "probability" in body
    assert "risk" in body
    assert "trade" in body


def test_live_market_analysis_uses_latest_candles():
    store = LiveCandleStore(
        max_candles=100
    )

    populate_store(
        store,
        total=80,
    )

    client = TestClient(
        create_app(
            live_candle_store=store
        )
    )

    payload = build_payload()
    payload["candle_limit"] = 60

    response = client.post(
        "/market/analyze",
        json=payload,
    )

    assert response.status_code == 200
    assert response.json()[
        "current_price"
    ] == 21721.0


def test_live_market_analysis_rejects_insufficient_candles():
    store = LiveCandleStore()
    populate_store(
        store,
        total=20,
    )

    client = TestClient(
        create_app(
            live_candle_store=store
        )
    )

    response = client.post(
        "/market/analyze",
        json=build_payload(),
    )

    assert response.status_code == 400

    body = response.json()

    assert "velas" in str(
        body
    ).lower()


def test_live_market_analysis_rejects_missing_market():
    store = LiveCandleStore()

    client = TestClient(
        create_app(
            live_candle_store=store
        )
    )

    response = client.post(
        "/market/analyze",
        json=build_payload(),
    )

    assert response.status_code == 400


def test_live_market_analysis_rejects_invalid_risk():
    store = LiveCandleStore()
    populate_store(store)

    client = TestClient(
        create_app(
            live_candle_store=store
        )
    )

    payload = build_payload()
    payload["risk_percent"] = 0

    response = client.post(
        "/market/analyze",
        json=payload,
    )

    assert response.status_code == 422
