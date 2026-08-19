from fastapi.testclient import TestClient

from backend.api.app import create_app


def build_trade_signal():
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



def test_live_position_monitor_updates_dashboard_realtime():
    app = create_app()

    client = TestClient(
        app
    )

    service = (
        app.state
        .trade_lifecycle_service_v2
    )

    monitor = (
        app.state
        .live_position_monitor_v2
    )

    submit_result = service.submit_signal(
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

    assert submit_result["accepted"] is True
    assert (
        submit_result["active_position_id"]
        is not None
    )

    active_positions = (
        service.get_active_positions()
    )

    assert len(active_positions) == 1

    position_id = active_positions[0][
        "position_id"
    ]

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

        monitor_result = monitor.process_price(
            symbol="NQ",
            current_price=105.0,
        )

        assert monitor_result["processed"] is True
        assert monitor_result["matched_positions"] == 1
        assert monitor_result["closed_positions"] == 0

        updated_message = (
            websocket.receive_json()
        )

        assert (
            updated_message["event_type"]
            == "dashboard_updated"
        )

        assert (
            updated_message["reason"]
            == "position_updated"
        )

        source_event = (
            updated_message[
                "source_event"
            ]
        )

        assert (
            source_event["event_type"]
            == "position_updated"
        )

        assert (
            source_event["payload"][
                "position_id"
            ]
            == position_id
        )

        assert (
            source_event["payload"][
                "current_price"
            ]
            == 105.0
        )

        assert (
            source_event["payload"][
                "status"
            ]
            == "OPEN"
        )

    positions_after = (
        service.get_active_positions()
    )

    assert len(positions_after) == 1

    assert (
        positions_after[0][
            "current_price"
        ]
        == 105.0
    )


def test_live_position_monitor_closes_trade_realtime():
    app = create_app()

    client = TestClient(
        app
    )

    service = (
        app.state
        .trade_lifecycle_service_v2
    )

    monitor = (
        app.state
        .live_position_monitor_v2
    )

    submit_result = service.submit_signal(
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

    assert submit_result["accepted"] is True

    active_positions = (
        service.get_active_positions()
    )

    assert len(active_positions) == 1

    position_id = active_positions[0][
        "position_id"
    ]

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

        monitor_result = monitor.process_price(
            symbol="NQ",
            current_price=110.0,
        )

        assert monitor_result["processed"] is True
        assert monitor_result["matched_positions"] == 1
        assert monitor_result["closed_positions"] == 1

        first_update = (
            websocket.receive_json()
        )

        second_update = (
            websocket.receive_json()
        )

        messages = [
            first_update,
            second_update,
        ]

        reasons = {
            message["reason"]
            for message in messages
        }

        assert "trade_closed" in reasons
        assert "position_updated" in reasons

        trade_closed_message = next(
            message
            for message in messages
            if (
                message["reason"]
                == "trade_closed"
            )
        )

        assert (
            trade_closed_message[
                "source_event"
            ]["payload"][
                "position_id"
            ]
            == position_id
        )

        assert (
            trade_closed_message[
                "source_event"
            ]["payload"][
                "status"
            ]
            == "CLOSED"
        )

    assert (
        service.get_active_positions()
        == []
    )

    history = service.get_trade_history()

    assert len(history) == 1

    assert (
        history[0]["position_id"]
        == position_id
    )
