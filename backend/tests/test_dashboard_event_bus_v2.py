import pytest

from backend.dashboard.dashboard_event_bus_v2 import (
    DashboardEventBusV2,
)


def build_bus():
    return DashboardEventBusV2()


def test_starts_empty():
    bus = build_bus()

    assert bus.get_subscriber_count() == 0
    assert bus.get_event_history() == []


def test_subscribes_listener():
    bus = build_bus()

    received = []

    def listener(event):
        received.append(event)

    result = bus.subscribe(
        event_type="trade_closed",
        listener=listener,
    )

    assert result["subscribed"] is True
    assert result["event_type"] == "trade_closed"
    assert bus.get_subscriber_count() == 1


def test_rejects_invalid_event_type():
    bus = build_bus()

    with pytest.raises(
        ValueError,
        match="event_type",
    ):
        bus.subscribe(
            event_type="",
            listener=lambda event: None,
        )


def test_rejects_invalid_listener():
    bus = build_bus()

    with pytest.raises(
        TypeError,
        match="listener",
    ):
        bus.subscribe(
            event_type="trade_closed",
            listener=object(),
        )


def test_publishes_event_to_listener():
    bus = build_bus()

    received = []

    def listener(event):
        received.append(event)

    bus.subscribe(
        event_type="trade_closed",
        listener=listener,
    )

    result = bus.publish(
        event_type="trade_closed",
        payload={
            "position_id": "pos-1",
            "realized_pnl": 250.0,
        },
    )

    assert result["published"] is True
    assert result["listeners_notified"] == 1

    assert len(received) == 1

    event = received[0]

    assert event["event_type"] == "trade_closed"
    assert event["payload"]["position_id"] == "pos-1"
    assert event["payload"]["realized_pnl"] == 250.0
    assert event["event_time"] is not None


def test_does_not_notify_other_event_types():
    bus = build_bus()

    received = []

    bus.subscribe(
        event_type="risk_blocked",
        listener=received.append,
    )

    result = bus.publish(
        event_type="trade_closed",
        payload={},
    )

    assert result["listeners_notified"] == 0
    assert received == []


def test_supports_multiple_listeners():
    bus = build_bus()

    received_one = []
    received_two = []

    bus.subscribe(
        event_type="portfolio_updated",
        listener=received_one.append,
    )

    bus.subscribe(
        event_type="portfolio_updated",
        listener=received_two.append,
    )

    result = bus.publish(
        event_type="portfolio_updated",
        payload={
            "total_pnl": 500.0,
        },
    )

    assert result["listeners_notified"] == 2
    assert len(received_one) == 1
    assert len(received_two) == 1


def test_unsubscribes_listener():
    bus = build_bus()

    received = []

    def listener(event):
        received.append(event)

    bus.subscribe(
        event_type="trade_opened",
        listener=listener,
    )

    result = bus.unsubscribe(
        event_type="trade_opened",
        listener=listener,
    )

    assert result["unsubscribed"] is True
    assert bus.get_subscriber_count() == 0

    bus.publish(
        event_type="trade_opened",
        payload={},
    )

    assert received == []


def test_records_event_history():
    bus = build_bus()

    bus.publish(
        event_type="trade_opened",
        payload={
            "position_id": "pos-1",
        },
    )

    bus.publish(
        event_type="trade_closed",
        payload={
            "position_id": "pos-1",
        },
    )

    history = bus.get_event_history()

    assert len(history) == 2
    assert history[0]["event_type"] == "trade_opened"
    assert history[1]["event_type"] == "trade_closed"


def test_event_history_is_a_copy():
    bus = build_bus()

    bus.publish(
        event_type="dashboard_refreshed",
        payload={},
    )

    history = bus.get_event_history()

    history.append(
        {
            "modified": True,
        }
    )

    fresh_history = bus.get_event_history()

    assert len(fresh_history) == 1


def test_rejects_invalid_payload_type():
    bus = build_bus()

    with pytest.raises(
        TypeError,
        match="payload",
    ):
        bus.publish(
            event_type="trade_closed",
            payload=object(),
        )


def test_listener_failure_does_not_stop_other_listeners():
    bus = build_bus()

    received = []

    def failing_listener(event):
        raise RuntimeError(
            "listener failure"
        )

    bus.subscribe(
        event_type="trade_closed",
        listener=failing_listener,
    )

    bus.subscribe(
        event_type="trade_closed",
        listener=received.append,
    )

    result = bus.publish(
        event_type="trade_closed",
        payload={},
    )

    assert result["listeners_notified"] == 1
    assert result["listener_errors"] == 1
    assert len(received) == 1
