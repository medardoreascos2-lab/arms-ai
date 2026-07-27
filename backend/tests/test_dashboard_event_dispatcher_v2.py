import pytest

from backend.dashboard.dashboard_event_dispatcher_v2 import (
    DashboardEventDispatcherV2,
)


class FakeEventBus:

    def __init__(self):
        self.subscriptions = []

    def subscribe(
        self,
        *,
        event_type,
        listener,
    ):
        self.subscriptions.append(
            {
                "event_type": event_type,
                "listener": listener,
            }
        )

        return {
            "subscribed": True,
            "event_type": event_type,
        }


class FakeRefreshService:

    def __init__(self):
        self.calls = []

    def refresh(
        self,
        *,
        reason,
        event,
    ):
        self.calls.append(
            {
                "reason": reason,
                "event": event,
            }
        )

        return {
            "refreshed": True,
            "reason": reason,
        }


def build_dispatcher(
    *,
    event_bus=None,
    refresh_service=None,
):
    return DashboardEventDispatcherV2(
        event_bus_v2=event_bus,
        refresh_service_v2=refresh_service,
    )


def test_accepts_none_dependencies():
    dispatcher = build_dispatcher()

    assert dispatcher.event_bus_v2 is None
    assert dispatcher.refresh_service_v2 is None


def test_rejects_invalid_event_bus():
    with pytest.raises(
        TypeError,
        match="event_bus_v2",
    ):
        build_dispatcher(
            event_bus=object(),
        )


def test_rejects_invalid_refresh_service():
    with pytest.raises(
        TypeError,
        match="refresh_service_v2",
    ):
        build_dispatcher(
            refresh_service=object(),
        )


def test_registers_default_subscriptions():
    event_bus = FakeEventBus()

    dispatcher = build_dispatcher(
        event_bus=event_bus,
        refresh_service=FakeRefreshService(),
    )

    result = dispatcher.register()

    assert result["registered"] is True
    assert result["subscription_count"] == 6

    event_types = {
        item["event_type"]
        for item in event_bus.subscriptions
    }

    assert event_types == {
        "trade_opened",
        "trade_closed",
        "position_updated",
        "portfolio_updated",
        "risk_updated",
        "dashboard_refresh",
    }


def test_register_without_event_bus():
    dispatcher = build_dispatcher(
        event_bus=None,
        refresh_service=FakeRefreshService(),
    )

    result = dispatcher.register()

    assert result["registered"] is False
    assert result["subscription_count"] == 0


def test_dispatches_trade_opened():
    refresh_service = FakeRefreshService()

    dispatcher = build_dispatcher(
        refresh_service=refresh_service,
    )

    event = {
        "event_type": "trade_opened",
        "payload": {
            "position_id": "pos-1",
        },
    }

    result = dispatcher.dispatch(
        event=event,
    )

    assert result["dispatched"] is True
    assert result["reason"] == "trade_opened"

    assert len(refresh_service.calls) == 1
    assert (
        refresh_service.calls[0]["reason"]
        == "trade_opened"
    )


def test_dispatches_risk_updated():
    refresh_service = FakeRefreshService()

    dispatcher = build_dispatcher(
        refresh_service=refresh_service,
    )

    result = dispatcher.dispatch(
        event={
            "event_type": "risk_updated",
            "payload": {
                "trading_blocked": True,
            },
        },
    )

    assert result["dispatched"] is True
    assert result["reason"] == "risk_updated"


def test_returns_false_without_refresh_service():
    dispatcher = build_dispatcher(
        refresh_service=None,
    )

    result = dispatcher.dispatch(
        event={
            "event_type": "trade_closed",
            "payload": {},
        },
    )

    assert result["dispatched"] is False
    assert result["reason"] == "no_refresh_service"


def test_rejects_invalid_event():
    dispatcher = build_dispatcher(
        refresh_service=FakeRefreshService(),
    )

    with pytest.raises(
        TypeError,
        match="event",
    ):
        dispatcher.dispatch(
            event=object(),
        )


def test_rejects_event_without_type():
    dispatcher = build_dispatcher(
        refresh_service=FakeRefreshService(),
    )

    with pytest.raises(
        ValueError,
        match="event_type",
    ):
        dispatcher.dispatch(
            event={
                "payload": {},
            },
        )


def test_forwards_complete_event():
    refresh_service = FakeRefreshService()

    dispatcher = build_dispatcher(
        refresh_service=refresh_service,
    )

    event = {
        "event_type": "portfolio_updated",
        "event_time": (
            "2026-07-26T01:00:00+00:00"
        ),
        "payload": {
            "total_pnl": 500.0,
        },
    }

    dispatcher.dispatch(
        event=event,
    )

    assert (
        refresh_service.calls[0]["event"]
        == event
    )
