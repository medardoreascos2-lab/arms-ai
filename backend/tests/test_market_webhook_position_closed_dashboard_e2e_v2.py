from datetime import datetime
from datetime import timezone

from fastapi.testclient import TestClient

from backend.api.app import create_app


def build_trade_signal() -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": (
            "NQ LONG ENTRY 100.0 "
            "SL 95.0 TP 110.0"
        ),
    }


def build_webhook_payload(
    *,
    close: float,
) -> dict[str, object]:
    return {
        "symbol": "NQ",
        "timeframe": "1M",
        "open": close - 1.0,
        "high": close + 1.0,
        "low": close - 2.0,
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


def test_position_closed_reaches_dashboard_websocket():
    app = create_app()

    client = TestClient(
        app
    )

    service = (
        app.state
        .trade_lifecycle_service_v2
    )

    submitted = service.submit_signal(
        signal=build_trade_signal(),
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

    assert submitted["accepted"] is True

    position_id = submitted[
        "active_position_id"
    ]

    assert position_id is not None

    with client.websocket_connect(
        "/api/v2/dashboard/ws"
    ) as websocket:

        initial_message = (
            websocket.receive_json()
        )

        assert (
            initial_message["event_type"]
            == "dashboard_snapshot"
        )

        response = client.post(
            "/market/webhook",
            headers={
                "X-ARMS-TOKEN": str(
                    app.state.webhook_token
                ),
            },
            json=build_webhook_payload(
                close=110.0,
            ),
        )

        assert (
            response.status_code
            == 201
        ), response.text

        payload = response.json()

        assert payload["status"] == "stored"

        assert (
            payload["market_data"][
                "processed"
            ]
            is True
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

        dashboard_message = (
            websocket.receive_json()
        )

        assert (
            dashboard_message[
                "event_type"
            ]
            == "dashboard_updated"
        )

        assert (
            dashboard_message["reason"]
            == "trade_closed"
        )

        source_event = (
            dashboard_message[
                "source_event"
            ]
        )

        assert (
            source_event["event_type"]
            == "trade_closed"
        )

        source_payload = (
            source_event["payload"]
        )

        assert (
            source_payload[
                "position_id"
            ]
            == position_id
        )

        assert (
            source_payload[
                "status"
            ]
            == "CLOSED"
        )

        assert (
            source_payload[
                "current_price"
            ]
            == 110.0
        )

    active_positions = (
        service.get_active_positions()
    )

    assert active_positions == []

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
