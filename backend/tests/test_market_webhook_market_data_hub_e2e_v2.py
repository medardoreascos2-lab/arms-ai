from datetime import datetime
from datetime import timedelta
from datetime import timezone

from fastapi.testclient import TestClient

from backend.api.app import create_app


def build_webhook_payload(
    *,
    timestamp: datetime,
    close: float = 22000.0,
) -> dict[str, object]:

    return {
        "symbol": "NQ",
        "timeframe": "1M",
        "open": close - 2.0,
        "high": close + 3.0,
        "low": close - 4.0,
        "close": close,
        "volume": 1000.0,
        "timestamp": (
            timestamp.isoformat()
        ),
        "directional_momentum": 0.0,
        "adverse_structure": False,
    }


def test_webhook_rejects_duplicate_market_price():
    app = create_app()

    client = TestClient(
        app
    )

    token = str(
        app.state.webhook_token
    )

    headers = {
        "X-ARMS-TOKEN": token,
    }

    first_timestamp = datetime.now(
        timezone.utc
    )

    second_timestamp = (
        first_timestamp
        + timedelta(
            minutes=1
        )
    )

    first_response = client.post(
        "/market/webhook",
        headers=headers,
        json=build_webhook_payload(
            timestamp=first_timestamp,
            close=22000.0,
        ),
    )

    assert (
        first_response.status_code
        == 201
    ), first_response.text

    hub_state_after_first = (
        app.state
        .market_data_hub_v2
        .get_state()
    )

    feed_state_after_first = (
        app.state
        .price_feed_service_v2
        .get_state()
    )

    assert (
        hub_state_after_first[
            "message_count"
        ]
        == 1
    )

    assert (
        hub_state_after_first[
            "processed_count"
        ]
        == 1
    )

    assert (
        hub_state_after_first[
            "duplicate_count"
        ]
        == 0
    )

    assert (
        feed_state_after_first[
            "price_count"
        ]
        == 1
    )

    assert (
        feed_state_after_first[
            "monitor_calls"
        ]
        == 1
    )

    second_response = client.post(
        "/market/webhook",
        headers=headers,
        json=build_webhook_payload(
            timestamp=second_timestamp,
            close=22000.0,
        ),
    )

    assert (
        second_response.status_code
        == 201
    ), second_response.text

    hub_state_after_second = (
        app.state
        .market_data_hub_v2
        .get_state()
    )

    feed_state_after_second = (
        app.state
        .price_feed_service_v2
        .get_state()
    )

    assert (
        hub_state_after_second[
            "message_count"
        ]
        == 2
    )

    assert (
        hub_state_after_second[
            "processed_count"
        ]
        == 1
    )

    assert (
        hub_state_after_second[
            "duplicate_count"
        ]
        == 1
    )

    assert (
        feed_state_after_second[
            "price_count"
        ]
        == 1
    )

    assert (
        feed_state_after_second[
            "monitor_calls"
        ]
        == 1
    )

    assert (
        hub_state_after_second[
            "last_symbol"
        ]
        == "NQ"
    )

    assert (
        hub_state_after_second[
            "last_price"
        ]
        == 22000.0
    )

    assert (
        hub_state_after_second[
            "last_source"
        ]
        == "TRADINGVIEW_WEBHOOK"
    )


def test_webhook_processes_new_price_after_duplicate():
    app = create_app()

    client = TestClient(
        app
    )

    headers = {
        "X-ARMS-TOKEN": str(
            app.state.webhook_token
        ),
    }

    start_time = datetime.now(
        timezone.utc
    )

    prices = (
        22000.0,
        22000.0,
        22001.0,
    )

    for index, price in enumerate(
        prices
    ):
        response = client.post(
            "/market/webhook",
            headers=headers,
            json=build_webhook_payload(
                timestamp=(
                    start_time
                    + timedelta(
                        minutes=index
                    )
                ),
                close=price,
            ),
        )

        assert (
            response.status_code
            == 201
        ), response.text

    hub_state = (
        app.state
        .market_data_hub_v2
        .get_state()
    )

    feed_state = (
        app.state
        .price_feed_service_v2
        .get_state()
    )

    assert (
        hub_state["message_count"]
        == 3
    )

    assert (
        hub_state["processed_count"]
        == 2
    )

    assert (
        hub_state["duplicate_count"]
        == 1
    )

    assert (
        feed_state["price_count"]
        == 2
    )

    assert (
        feed_state["monitor_calls"]
        == 2
    )

    assert (
        feed_state["last_price"]
        == 22001.0
    )
