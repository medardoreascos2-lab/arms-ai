import asyncio

import pytest

from backend.dashboard.dashboard_websocket_hub_v2 import (
    DashboardWebSocketHubV2,
)


class FakeWebSocket:

    def __init__(
        self,
        *,
        fail_send=False,
    ):
        self.accepted = False
        self.sent_messages = []
        self.fail_send = fail_send

    async def accept(self):
        self.accepted = True

    async def send_json(
        self,
        payload,
    ):
        if self.fail_send:
            raise RuntimeError(
                "send failure"
            )

        self.sent_messages.append(
            payload
        )


def build_hub():
    return DashboardWebSocketHubV2()


def test_starts_empty():
    hub = build_hub()

    assert hub.get_connection_count() == 0

    state = hub.get_state()

    assert state["connection_count"] == 0
    assert state["broadcast_count"] == 0
    assert state["messages_sent"] == 0
    assert state["send_errors"] == 0
    assert state["last_broadcast_time"] is None


def test_connects_websocket():
    hub = build_hub()
    websocket = FakeWebSocket()

    result = asyncio.run(
        hub.connect(
            websocket=websocket,
        )
    )

    assert result["connected"] is True
    assert result["connection_count"] == 1
    assert websocket.accepted is True
    assert hub.get_connection_count() == 1


def test_rejects_invalid_websocket():
    hub = build_hub()

    with pytest.raises(
        TypeError,
        match="websocket",
    ):
        asyncio.run(
            hub.connect(
                websocket=object(),
            )
        )


def test_does_not_duplicate_connection():
    hub = build_hub()
    websocket = FakeWebSocket()

    asyncio.run(
        hub.connect(
            websocket=websocket,
        )
    )

    result = asyncio.run(
        hub.connect(
            websocket=websocket,
        )
    )

    assert result["connected"] is False
    assert result["reason"] == "already_connected"
    assert result["connection_count"] == 1


def test_disconnects_websocket():
    hub = build_hub()
    websocket = FakeWebSocket()

    asyncio.run(
        hub.connect(
            websocket=websocket,
        )
    )

    result = hub.disconnect(
        websocket=websocket,
    )

    assert result["disconnected"] is True
    assert result["connection_count"] == 0
    assert hub.get_connection_count() == 0


def test_disconnects_unknown_websocket():
    hub = build_hub()

    result = hub.disconnect(
        websocket=FakeWebSocket(),
    )

    assert result["disconnected"] is False
    assert result["reason"] == "not_connected"


def test_broadcasts_to_all_connections():
    hub = build_hub()

    websocket_one = FakeWebSocket()
    websocket_two = FakeWebSocket()

    asyncio.run(
        hub.connect(
            websocket=websocket_one,
        )
    )

    asyncio.run(
        hub.connect(
            websocket=websocket_two,
        )
    )

    payload = {
        "event_type": "dashboard_updated",
        "dashboard_status": "READY",
        "widget_count": 8,
    }

    result = asyncio.run(
        hub.broadcast(
            payload=payload,
        )
    )

    assert result["broadcasted"] is True
    assert result["connections_targeted"] == 2
    assert result["messages_sent"] == 2
    assert result["send_errors"] == 0

    assert websocket_one.sent_messages == [
        payload
    ]

    assert websocket_two.sent_messages == [
        payload
    ]


def test_broadcast_without_connections():
    hub = build_hub()

    result = asyncio.run(
        hub.broadcast(
            payload={
                "event_type": "dashboard_updated",
            },
        )
    )

    assert result["broadcasted"] is True
    assert result["connections_targeted"] == 0
    assert result["messages_sent"] == 0
    assert result["send_errors"] == 0


def test_rejects_invalid_payload():
    hub = build_hub()

    with pytest.raises(
        TypeError,
        match="payload",
    ):
        asyncio.run(
            hub.broadcast(
                payload=object(),
            )
        )


def test_send_failure_does_not_stop_other_connections():
    hub = build_hub()

    failing_websocket = FakeWebSocket(
        fail_send=True,
    )

    working_websocket = FakeWebSocket()

    asyncio.run(
        hub.connect(
            websocket=failing_websocket,
        )
    )

    asyncio.run(
        hub.connect(
            websocket=working_websocket,
        )
    )

    result = asyncio.run(
        hub.broadcast(
            payload={
                "event_type": "dashboard_updated",
            },
        )
    )

    assert result["connections_targeted"] == 2
    assert result["messages_sent"] == 1
    assert result["send_errors"] == 1

    assert len(
        working_websocket.sent_messages
    ) == 1


def test_failed_connection_is_removed():
    hub = build_hub()

    failing_websocket = FakeWebSocket(
        fail_send=True,
    )

    asyncio.run(
        hub.connect(
            websocket=failing_websocket,
        )
    )

    asyncio.run(
        hub.broadcast(
            payload={
                "event_type": "dashboard_updated",
            },
        )
    )

    assert hub.get_connection_count() == 0


def test_tracks_broadcast_state():
    hub = build_hub()
    websocket = FakeWebSocket()

    asyncio.run(
        hub.connect(
            websocket=websocket,
        )
    )

    asyncio.run(
        hub.broadcast(
            payload={
                "event_type": "dashboard_updated",
            },
        )
    )

    state = hub.get_state()

    assert state["connection_count"] == 1
    assert state["broadcast_count"] == 1
    assert state["messages_sent"] == 1
    assert state["send_errors"] == 0
    assert state["last_broadcast_time"] is not None


def test_state_is_a_copy():
    hub = build_hub()

    state = hub.get_state()

    state["broadcast_count"] = 999

    fresh_state = hub.get_state()

    assert fresh_state["broadcast_count"] == 0
