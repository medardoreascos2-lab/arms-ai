from datetime import datetime
from datetime import timedelta
from datetime import timezone

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.models.candle import Candle
from backend.trend.trend_engine_v2 import (
    TrendEngineV2,
)


def seed_candles(
    *,
    app,
    closes: list[float],
) -> None:
    start = datetime(
        2026,
        7,
        27,
        20,
        0,
        tzinfo=timezone.utc,
    )

    for index, close in enumerate(
        closes
    ):
        app.state.live_candle_store.add(
            Candle(
                symbol="NQ",
                timeframe="1M",
                open=close - 0.5,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1000.0 + index,
                timestamp=(
                    start
                    + timedelta(
                        minutes=index
                    )
                ),
            )
        )


def test_app_publishes_shared_trend_engine():
    app = create_app()

    assert isinstance(
        app.state.trend_engine_v2,
        TrendEngineV2,
    )

    assert (
        app.state
        .trend_engine_v2
        .live_candle_store
        is app.state.live_candle_store
    )


def test_webhook_returns_insufficient_data():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": str(
                app.state.webhook_token
            ),
        },
        json={
            "symbol": "NQ",
            "timeframe": "1M",
            "open": 22999.0,
            "high": 23002.0,
            "low": 22998.0,
            "close": 23000.0,
            "volume": 1000.0,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "directional_momentum": 0.0,
            "adverse_structure": False,
        },
    )

    assert response.status_code == 201

    trend = response.json()["trend"]

    assert (
        trend["status"]
        == "INSUFFICIENT_DATA"
    )

    assert (
        trend["direction"]
        == "INSUFFICIENT_DATA"
    )


def test_webhook_returns_bullish_trend():
    app = create_app()
    client = TestClient(app)

    seed_candles(
        app=app,
        closes=[
            23000.0 + index * 2.0
            for index in range(49)
        ],
    )

    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": str(
                app.state.webhook_token
            ),
        },
        json={
            "symbol": "NQ",
            "timeframe": "1M",
            "open": 23097.5,
            "high": 23100.0,
            "low": 23096.0,
            "close": 23098.0,
            "volume": 1100.0,
            "timestamp": datetime(
                2026,
                7,
                27,
                20,
                49,
                tzinfo=timezone.utc,
            ).isoformat(),
            "directional_momentum": 0.0,
            "adverse_structure": False,
        },
    )

    assert response.status_code == 201

    trend = response.json()["trend"]

    assert trend["status"] == "READY"
    assert trend["direction"] == "BULLISH"
    assert (
        trend["fast_ema"]
        > trend["slow_ema"]
    )
    assert trend["slope"] > 0
