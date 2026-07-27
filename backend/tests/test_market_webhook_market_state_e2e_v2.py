from datetime import datetime
from datetime import timezone

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.market_state.market_state_engine_v2 import (
    MarketStateEngineV2,
)


def build_payload(
    *,
    close: float,
    timestamp: datetime,
) -> dict[str, object]:
    return {
        "symbol": "NQ",
        "timeframe": "1M",
        "open": close - 2.0,
        "high": close + 3.0,
        "low": close - 4.0,
        "close": close,
        "volume": 1000.0,
        "timestamp": timestamp.isoformat(),
        "directional_momentum": 0.0,
        "adverse_structure": False,
    }


def test_app_publishes_shared_market_state_engine():
    app = create_app()

    engine = (
        app.state
        .market_state_engine_v2
    )

    hub = (
        app.state
        .market_data_hub_v2
    )

    assert isinstance(
        engine,
        MarketStateEngineV2,
    )

    assert (
        hub.market_state_engine_v2
        is engine
    )


def test_webhook_updates_market_state():
    app = create_app()
    client = TestClient(app)

    timestamp = datetime(
        2026,
        7,
        27,
        20,
        30,
        tzinfo=timezone.utc,
    )

    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": str(
                app.state.webhook_token
            ),
        },
        json=build_payload(
            close=23000.25,
            timestamp=timestamp,
        ),
    )

    assert (
        response.status_code
        == 201
    ), response.text

    payload = response.json()

    market_data = payload[
        "market_data"
    ]

    assert (
        market_data[
            "processed"
        ]
        is True
    )

    assert (
        market_data[
            "market_state_updated"
        ]
        is True
    )

    assert (
        market_data[
            "market_state_error"
        ]
        is False
    )

    state = (
        app.state
        .market_state_engine_v2
        .get(
            symbol="NQ",
            timeframe="1M",
        )
    )

    assert state is not None
    assert state.symbol == "NQ"
    assert state.timeframe == "1M"
    assert state.last_price == 23000.25
    assert state.timestamp == timestamp


def test_duplicate_webhook_does_not_replace_market_state():
    app = create_app()
    client = TestClient(app)

    first_timestamp = datetime(
        2026,
        7,
        27,
        20,
        30,
        tzinfo=timezone.utc,
    )

    duplicate_timestamp = datetime(
        2026,
        7,
        27,
        20,
        31,
        tzinfo=timezone.utc,
    )

    headers = {
        "X-ARMS-TOKEN": str(
            app.state.webhook_token
        ),
    }

    first = client.post(
        "/market/webhook",
        headers=headers,
        json=build_payload(
            close=23000.25,
            timestamp=first_timestamp,
        ),
    )

    assert first.status_code == 201

    duplicate = client.post(
        "/market/webhook",
        headers=headers,
        json=build_payload(
            close=23000.25,
            timestamp=duplicate_timestamp,
        ),
    )

    assert duplicate.status_code == 201

    duplicate_data = (
        duplicate.json()[
            "market_data"
        ]
    )

    assert (
        duplicate_data["duplicate"]
        is True
    )

    assert (
        duplicate_data[
            "market_state_updated"
        ]
        is False
    )

    state = (
        app.state
        .market_state_engine_v2
        .get(
            symbol="NQ",
            timeframe="1M",
        )
    )

    assert state is not None
    assert state.timestamp == first_timestamp
