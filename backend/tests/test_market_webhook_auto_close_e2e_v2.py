from datetime import datetime
from datetime import timezone

from fastapi.testclient import TestClient

from backend.api.app import create_app


def build_trade_signal(
    *,
    direction: str,
) -> dict[str, object]:

    if direction == "LONG":
        stop_loss = 95.0
        take_profit = 110.0
    else:
        stop_loss = 105.0
        take_profit = 90.0

    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": direction,
        "entry_price": 100.0,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": (
            f"NQ {direction} ENTRY 100.0 "
            f"SL {stop_loss} "
            f"TP {take_profit}"
        ),
    }


def build_webhook_payload(
    *,
    close: float,
) -> dict[str, object]:

    return {
        "symbol": "NQ",
        "timeframe": "1M",
        "open": close,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": 1000.0,
        "timestamp": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "directional_momentum": 0.0,
        "adverse_structure": False,
    }


def submit_position(
    *,
    app,
    direction: str,
) -> str:

    service = (
        app.state
        .trade_lifecycle_service_v2
    )

    result = service.submit_signal(
        signal=build_trade_signal(
            direction=direction,
        ),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.3,
            "point_value": 2.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
            "current_price": 100.0,
        },
        order_context={
            "market_is_open": True,
        },
    )

    assert result["accepted"] is True

    position_id = result[
        "active_position_id"
    ]

    assert position_id is not None

    return str(
        position_id
    )


def send_market_price(
    *,
    app,
    client: TestClient,
    close: float,
) -> dict[str, object]:

    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": str(
                app.state.webhook_token
            ),
        },
        json=build_webhook_payload(
            close=close,
        ),
    )

    assert (
        response.status_code
        == 201
    ), response.text

    return response.json()


def test_long_position_closes_at_take_profit():
    app = create_app()

    client = TestClient(
        app
    )

    service = (
        app.state
        .trade_lifecycle_service_v2
    )

    position_id = submit_position(
        app=app,
        direction="LONG",
    )

    positions_before = (
        service.get_active_positions()
    )

    assert len(positions_before) == 1

    assert (
        positions_before[0][
            "position_id"
        ]
        == position_id
    )

    payload = send_market_price(
        app=app,
        client=client,
        close=110.0,
    )

    assert payload["status"] == "stored"

    assert (
        payload["market_data"][
            "processed"
        ]
        is True
    )

    assert (
        payload["market_data"][
            "duplicate"
        ]
        is False
    )

    assert (
        payload["price_feed"][
            "monitor_processed"
        ]
        is True
    )

    monitor_result = (
        payload["price_feed"][
            "monitor_result"
        ]
    )

    assert (
        monitor_result[
            "matched_positions"
        ]
        == 1
    )

    assert (
        monitor_result[
            "closed_positions"
        ]
        == 1
    )

    positions_after = (
        service.get_active_positions()
    )

    assert positions_after == []

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

    assert hub_state["message_count"] == 1
    assert hub_state["processed_count"] == 1
    assert hub_state["duplicate_count"] == 0

    assert feed_state["price_count"] == 1
    assert feed_state["monitor_calls"] == 1
    assert feed_state["monitor_errors"] == 0


def test_short_position_closes_at_take_profit():
    app = create_app()

    client = TestClient(
        app
    )

    service = (
        app.state
        .trade_lifecycle_service_v2
    )

    position_id = submit_position(
        app=app,
        direction="SHORT",
    )

    positions_before = (
        service.get_active_positions()
    )

    assert len(positions_before) == 1

    assert (
        positions_before[0][
            "position_id"
        ]
        == position_id
    )

    payload = send_market_price(
        app=app,
        client=client,
        close=90.0,
    )

    monitor_result = (
        payload["price_feed"][
            "monitor_result"
        ]
    )

    assert (
        monitor_result[
            "matched_positions"
        ]
        == 1
    )

    assert (
        monitor_result[
            "closed_positions"
        ]
        == 1
    )

    positions_after = (
        service.get_active_positions()
    )

    assert positions_after == []


def test_long_position_closes_at_stop_loss():
    app = create_app()

    client = TestClient(
        app
    )

    service = (
        app.state
        .trade_lifecycle_service_v2
    )

    submit_position(
        app=app,
        direction="LONG",
    )

    payload = send_market_price(
        app=app,
        client=client,
        close=95.0,
    )

    monitor_result = (
        payload["price_feed"][
            "monitor_result"
        ]
    )

    assert (
        monitor_result[
            "matched_positions"
        ]
        == 1
    )

    assert (
        monitor_result[
            "closed_positions"
        ]
        == 1
    )

    assert (
        service.get_active_positions()
        == []
    )


def test_short_position_closes_at_stop_loss():
    app = create_app()

    client = TestClient(
        app
    )

    service = (
        app.state
        .trade_lifecycle_service_v2
    )

    submit_position(
        app=app,
        direction="SHORT",
    )

    payload = send_market_price(
        app=app,
        client=client,
        close=105.0,
    )

    monitor_result = (
        payload["price_feed"][
            "monitor_result"
        ]
    )

    assert (
        monitor_result[
            "matched_positions"
        ]
        == 1
    )

    assert (
        monitor_result[
            "closed_positions"
        ]
        == 1
    )

    assert (
        service.get_active_positions()
        == []
    )
