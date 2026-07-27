from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_app_realtime_dashboard_e2e():
    app = create_app()

    required_state = (
        "dashboard_event_bus_v2",
        "dashboard_refresh_service_v2",
        "dashboard_event_dispatcher_v2",
        "dashboard_auto_refresh_engine_v2",
        "dashboard_websocket_hub_v2",
        "dashboard_websocket_broadcaster_v2",
    )

    for name in required_state:
        assert hasattr(
            app.state,
            name,
        ), f"Falta app.state.{name}"

    client = TestClient(
        app
    )

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

        refresh_state_before = (
            app.state
            .dashboard_refresh_service_v2
            .get_state()
        )

        publish_result = (
            app.state
            .dashboard_auto_refresh_engine_v2
            .publish_event(
                event_type="trade_opened",
                payload={
                    "position_id": "e2e-pos-1",
                    "symbol": "NQ",
                    "direction": "LONG",
                    "quantity": 1,
                    "entry_price": 22000.0,
                },
            )
        )

        assert (
            publish_result["published"]
            is True
        )

        assert (
            publish_result[
                "listeners_notified"
            ]
            == 1
        )

        assert (
            publish_result[
                "listener_errors"
            ]
            == 0
        )

        updated_message = (
            websocket.receive_json()
        )

        assert (
            updated_message["event_type"]
            == "dashboard_updated"
        )

        assert (
            updated_message["reason"]
            == "trade_opened"
        )

        assert (
            updated_message[
                "source_event"
            ]["event_type"]
            == "trade_opened"
        )

        assert (
            updated_message[
                "source_event"
            ]["payload"][
                "position_id"
            ]
            == "e2e-pos-1"
        )

        assert (
            updated_message[
                "dashboard"
            ]
            is not None
        )

        assert (
            updated_message[
                "widgets"
            ]
            is not None
        )

        refresh_state_after = (
            app.state
            .dashboard_refresh_service_v2
            .get_state()
        )

        assert (
            refresh_state_after[
                "refresh_count"
            ]
            == (
                refresh_state_before[
                    "refresh_count"
                ]
                + 1
            )
        )

        assert (
            refresh_state_after[
                "last_reason"
            ]
            == "trade_opened"
        )

    hub_state = (
        app.state
        .dashboard_websocket_hub_v2
        .get_state()
    )

    assert (
        hub_state["connection_count"]
        == 0
    )

    assert (
        hub_state["messages_sent"]
        >= 1
    )

    assert (
        hub_state["send_errors"]
        == 0
    )
