import asyncio

import pytest

from backend.dashboard.dashboard_websocket_broadcaster_v2 import (
    DashboardWebSocketBroadcasterV2,
)


class FakeRefreshService:

    def __init__(
        self,
        *,
        snapshot=None,
        widgets=None,
    ):
        self.snapshot = snapshot
        self.widgets = widgets

    def get_cached_snapshot(self):
        return self.snapshot

    def get_cached_widgets(self):
        return self.widgets


class FakeWebSocketHub:

    def __init__(self):
        self.payloads = []

    async def broadcast(
        self,
        *,
        payload,
    ):
        self.payloads.append(
            payload
        )

        return {
            "broadcasted": True,
            "connections_targeted": 2,
            "messages_sent": 2,
            "send_errors": 0,
        }


def build_broadcaster(
    *,
    refresh_service=None,
    websocket_hub=None,
):
    return DashboardWebSocketBroadcasterV2(
        refresh_service_v2=(
            refresh_service
        ),
        websocket_hub_v2=(
            websocket_hub
        ),
    )


def test_accepts_none_dependencies():
    broadcaster = build_broadcaster()

    assert broadcaster.refresh_service_v2 is None
    assert broadcaster.websocket_hub_v2 is None


def test_rejects_invalid_refresh_service():
    with pytest.raises(
        TypeError,
        match="refresh_service_v2",
    ):
        build_broadcaster(
            refresh_service=object(),
        )


def test_rejects_invalid_websocket_hub():
    with pytest.raises(
        TypeError,
        match="websocket_hub_v2",
    ):
        build_broadcaster(
            websocket_hub=object(),
        )


def test_broadcasts_dashboard_update():
    refresh_service = FakeRefreshService(
        snapshot={
            "dashboard_status": "READY",
            "performance_score": {
                "score": 92,
            },
        },
        widgets={
            "status": "READY",
            "widget_count": 8,
            "widgets": {},
        },
    )

    websocket_hub = FakeWebSocketHub()

    broadcaster = build_broadcaster(
        refresh_service=refresh_service,
        websocket_hub=websocket_hub,
    )

    result = asyncio.run(
        broadcaster.broadcast_update(
            reason="trade_closed",
            event={
                "event_type": "trade_closed",
                "payload": {
                    "position_id": "pos-1",
                },
            },
        )
    )

    assert result["broadcasted"] is True
    assert result["reason"] == "trade_closed"
    assert result["messages_sent"] == 2

    assert len(
        websocket_hub.payloads
    ) == 1

    payload = websocket_hub.payloads[0]

    assert (
        payload["event_type"]
        == "dashboard_updated"
    )

    assert payload["reason"] == "trade_closed"

    assert (
        payload["dashboard"][
            "performance_score"
        ]["score"]
        == 92
    )

    assert (
        payload["widgets"][
            "widget_count"
        ]
        == 8
    )

    assert (
        payload["source_event"][
            "event_type"
        ]
        == "trade_closed"
    )


def test_broadcasts_none_cached_data():
    websocket_hub = FakeWebSocketHub()

    broadcaster = build_broadcaster(
        refresh_service=(
            FakeRefreshService()
        ),
        websocket_hub=websocket_hub,
    )

    result = asyncio.run(
        broadcaster.broadcast_update(
            reason="dashboard_refresh",
            event={
                "event_type":
                    "dashboard_refresh",
                "payload": {},
            },
        )
    )

    assert result["broadcasted"] is True

    payload = websocket_hub.payloads[0]

    assert payload["dashboard"] is None
    assert payload["widgets"] is None


def test_returns_false_without_websocket_hub():
    broadcaster = build_broadcaster(
        refresh_service=(
            FakeRefreshService()
        ),
        websocket_hub=None,
    )

    result = asyncio.run(
        broadcaster.broadcast_update(
            reason="trade_closed",
            event={
                "event_type": "trade_closed",
                "payload": {},
            },
        )
    )

    assert result["broadcasted"] is False
    assert result["reason"] == "no_websocket_hub"


def test_returns_false_without_refresh_service():
    broadcaster = build_broadcaster(
        refresh_service=None,
        websocket_hub=(
            FakeWebSocketHub()
        ),
    )

    result = asyncio.run(
        broadcaster.broadcast_update(
            reason="trade_closed",
            event={
                "event_type": "trade_closed",
                "payload": {},
            },
        )
    )

    assert result["broadcasted"] is False
    assert result["reason"] == "no_refresh_service"


def test_rejects_invalid_reason():
    broadcaster = build_broadcaster()

    with pytest.raises(
        ValueError,
        match="reason",
    ):
        asyncio.run(
            broadcaster.broadcast_update(
                reason="",
                event={},
            )
        )


def test_rejects_invalid_event():
    broadcaster = build_broadcaster()

    with pytest.raises(
        TypeError,
        match="event",
    ):
        asyncio.run(
            broadcaster.broadcast_update(
                reason="trade_closed",
                event=object(),
            )
        )


def test_payload_is_copied():
    snapshot = {
        "nested": {
            "value": 1,
        },
    }

    refresh_service = FakeRefreshService(
        snapshot=snapshot,
        widgets={
            "widgets": {},
        },
    )

    websocket_hub = FakeWebSocketHub()

    broadcaster = build_broadcaster(
        refresh_service=refresh_service,
        websocket_hub=websocket_hub,
    )

    asyncio.run(
        broadcaster.broadcast_update(
            reason="trade_closed",
            event={
                "event_type": "trade_closed",
                "payload": {},
            },
        )
    )

    snapshot["nested"]["value"] = 999

    assert (
        websocket_hub.payloads[0][
            "dashboard"
        ]["nested"]["value"]
        == 1
    )
