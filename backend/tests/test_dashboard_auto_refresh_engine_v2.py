import pytest

from backend.dashboard.dashboard_auto_refresh_engine_v2 import (
    DashboardAutoRefreshEngineV2,
)


class FakeEventBus:

    def __init__(self):
        self.published_events = []

    def publish(
        self,
        *,
        event_type,
        payload,
    ):
        self.published_events.append(
            {
                "event_type": event_type,
                "payload": payload,
            }
        )

        return {
            "published": True,
            "listeners_notified": 1,
            "listener_errors": 0,
        }


class FakeDispatcher:

    def __init__(self):
        self.register_calls = 0

    def register(self):
        self.register_calls += 1

        return {
            "registered": True,
            "subscription_count": 6,
        }


class FakeRefreshService:

    def __init__(self):
        self.refresh_calls = []

    def refresh(
        self,
        *,
        reason,
        event,
    ):
        self.refresh_calls.append(
            {
                "reason": reason,
                "event": event,
            }
        )

        return {
            "refreshed": True,
            "reason": reason,
            "refresh_count": len(
                self.refresh_calls
            ),
            "snapshot_updated": True,
            "widgets_updated": True,
        }

    def get_state(self):
        return {
            "refresh_count": len(
                self.refresh_calls
            ),
            "last_reason": (
                self.refresh_calls[-1]["reason"]
                if self.refresh_calls
                else None
            ),
        }


def build_engine(
    *,
    event_bus=None,
    dispatcher=None,
    refresh_service=None,
):
    return DashboardAutoRefreshEngineV2(
        event_bus_v2=event_bus,
        event_dispatcher_v2=dispatcher,
        refresh_service_v2=refresh_service,
    )


def test_accepts_none_dependencies():
    engine = build_engine()

    assert engine.event_bus_v2 is None
    assert engine.event_dispatcher_v2 is None
    assert engine.refresh_service_v2 is None


def test_rejects_invalid_event_bus():
    with pytest.raises(
        TypeError,
        match="event_bus_v2",
    ):
        build_engine(
            event_bus=object(),
        )


def test_rejects_invalid_dispatcher():
    with pytest.raises(
        TypeError,
        match="event_dispatcher_v2",
    ):
        build_engine(
            dispatcher=object(),
        )


def test_rejects_invalid_refresh_service():
    with pytest.raises(
        TypeError,
        match="refresh_service_v2",
    ):
        build_engine(
            refresh_service=object(),
        )


def test_starts_inactive():
    engine = build_engine()

    state = engine.get_state()

    assert state["started"] is False
    assert state["start_count"] == 0
    assert state["last_start_time"] is None
    assert state["last_registration"] is None
    assert state["last_initial_refresh"] is None


def test_start_registers_dispatcher():
    dispatcher = FakeDispatcher()

    engine = build_engine(
        dispatcher=dispatcher,
    )

    result = engine.start()

    assert result["started"] is True
    assert result["registered"] is True
    assert result["subscription_count"] == 6
    assert dispatcher.register_calls == 1


def test_start_runs_initial_refresh():
    refresh_service = FakeRefreshService()

    engine = build_engine(
        refresh_service=refresh_service,
    )

    result = engine.start()

    assert result["started"] is True
    assert result["initial_refresh"] is True
    assert len(refresh_service.refresh_calls) == 1

    call = refresh_service.refresh_calls[0]

    assert call["reason"] == "initial_startup"
    assert (
        call["event"]["event_type"]
        == "dashboard_refresh"
    )


def test_start_without_dependencies():
    engine = build_engine()

    result = engine.start()

    assert result["started"] is True
    assert result["registered"] is False
    assert result["subscription_count"] == 0
    assert result["initial_refresh"] is False


def test_start_updates_state():
    engine = build_engine(
        dispatcher=FakeDispatcher(),
        refresh_service=FakeRefreshService(),
    )

    engine.start()

    state = engine.get_state()

    assert state["started"] is True
    assert state["start_count"] == 1
    assert state["last_start_time"] is not None

    assert (
        state["last_registration"][
            "subscription_count"
        ]
        == 6
    )

    assert (
        state["last_initial_refresh"][
            "refreshed"
        ]
        is True
    )


def test_start_can_run_multiple_times():
    engine = build_engine(
        dispatcher=FakeDispatcher(),
        refresh_service=FakeRefreshService(),
    )

    engine.start()
    result = engine.start()

    assert result["start_count"] == 2
    assert engine.get_state()["start_count"] == 2


def test_publish_event_uses_event_bus():
    event_bus = FakeEventBus()

    engine = build_engine(
        event_bus=event_bus,
    )

    result = engine.publish_event(
        event_type="trade_closed",
        payload={
            "position_id": "pos-1",
        },
    )

    assert result["published"] is True
    assert len(event_bus.published_events) == 1

    assert (
        event_bus.published_events[0][
            "event_type"
        ]
        == "trade_closed"
    )


def test_publish_event_without_event_bus():
    engine = build_engine()

    result = engine.publish_event(
        event_type="trade_closed",
        payload={},
    )

    assert result["published"] is False
    assert result["reason"] == "no_event_bus"


def test_rejects_invalid_event_type():
    engine = build_engine(
        event_bus=FakeEventBus(),
    )

    with pytest.raises(
        ValueError,
        match="event_type",
    ):
        engine.publish_event(
            event_type="",
            payload={},
        )


def test_rejects_invalid_payload():
    engine = build_engine(
        event_bus=FakeEventBus(),
    )

    with pytest.raises(
        TypeError,
        match="payload",
    ):
        engine.publish_event(
            event_type="trade_closed",
            payload=object(),
        )


def test_get_state_is_a_copy():
    engine = build_engine()

    state = engine.get_state()
    state["start_count"] = 999

    fresh_state = engine.get_state()

    assert fresh_state["start_count"] == 0
