import asyncio

from backend.dashboard.dashboard_event_dispatcher_v2 import (
    DashboardEventDispatcherV2,
)


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
            "refresh_count": len(
                self.calls
            ),
        }


class FakeBroadcaster:

    def __init__(self):
        self.calls = []

    async def broadcast_update(
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
            "broadcasted": True,
            "reason": reason,
            "messages_sent": 1,
        }


def build_dispatcher(
    *,
    refresh_service=None,
    broadcaster=None,
):
    return DashboardEventDispatcherV2(
        event_bus_v2=None,
        refresh_service_v2=(
            refresh_service
        ),
        websocket_broadcaster_v2=(
            broadcaster
        ),
    )


def test_accepts_websocket_broadcaster():
    broadcaster = FakeBroadcaster()

    dispatcher = build_dispatcher(
        broadcaster=broadcaster,
    )

    assert (
        dispatcher.websocket_broadcaster_v2
        is broadcaster
    )


def test_dispatch_refreshes_and_broadcasts():
    refresh_service = FakeRefreshService()
    broadcaster = FakeBroadcaster()

    dispatcher = build_dispatcher(
        refresh_service=refresh_service,
        broadcaster=broadcaster,
    )

    event = {
        "event_type": "trade_closed",
        "payload": {
            "position_id": "pos-1",
        },
    }

    result = dispatcher.dispatch(
        event=event,
    )

    assert result["dispatched"] is True
    assert result["reason"] == "trade_closed"
    assert result["broadcast_scheduled"] is True

    assert len(refresh_service.calls) == 1
    assert len(broadcaster.calls) == 1

    assert (
        broadcaster.calls[0]["reason"]
        == "trade_closed"
    )

    assert (
        broadcaster.calls[0]["event"]
        == event
    )


def test_dispatch_without_broadcaster():
    refresh_service = FakeRefreshService()

    dispatcher = build_dispatcher(
        refresh_service=refresh_service,
        broadcaster=None,
    )

    result = dispatcher.dispatch(
        event={
            "event_type": "portfolio_updated",
            "payload": {},
        },
    )

    assert result["dispatched"] is True
    assert result["broadcast_scheduled"] is False


def test_rejects_invalid_broadcaster():
    try:
        build_dispatcher(
            broadcaster=object(),
        )
    except TypeError as exc:
        assert (
            "websocket_broadcaster_v2"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )


def test_broadcast_failure_does_not_break_dispatch():
    class FailingBroadcaster:

        async def broadcast_update(
            self,
            *,
            reason,
            event,
        ):
            raise RuntimeError(
                "broadcast failure"
            )

    dispatcher = build_dispatcher(
        refresh_service=(
            FakeRefreshService()
        ),
        broadcaster=(
            FailingBroadcaster()
        ),
    )

    result = dispatcher.dispatch(
        event={
            "event_type": "risk_updated",
            "payload": {},
        },
    )

    assert result["dispatched"] is True
    assert result["broadcast_scheduled"] is False
    assert result["broadcast_error"] is True
