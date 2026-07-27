import asyncio

import pytest

from backend.dashboard.dashboard_auto_refresh_engine_v2 import (
    DashboardAutoRefreshEngineV2,
)
from backend.dashboard.dashboard_event_bus_v2 import (
    DashboardEventBusV2,
)
from backend.dashboard.dashboard_event_dispatcher_v2 import (
    DashboardEventDispatcherV2,
)
from backend.dashboard.dashboard_refresh_service_v2 import (
    DashboardRefreshServiceV2,
)
from backend.dashboard.dashboard_websocket_broadcaster_v2 import (
    DashboardWebSocketBroadcasterV2,
)
from backend.dashboard.dashboard_websocket_hub_v2 import (
    DashboardWebSocketHubV2,
)


class FakeLiveDataService:

    def __init__(self):
        self.calls = 0

    def get_snapshot(self):
        self.calls += 1

        return {
            "snapshot_time": (
                f"2026-07-26T04:00:0{self.calls}+00:00"
            ),
            "dashboard_status": "READY",
            "performance_score": {
                "score": 90 + self.calls,
                "grade": "A+",
            },
        }


class FakeWidgetRegistry:

    def __init__(self):
        self.calls = 0

    def render_all(self):
        self.calls += 1

        return {
            "status": "READY",
            "widget_count": 1,
            "widgets": {
                "performance_score": {
                    "widget": "performance_score",
                    "status": "READY",
                    "data": {
                        "score": 90 + self.calls,
                    },
                },
            },
        }


class FakeWebSocket:

    def __init__(self):
        self.accepted = False
        self.sent_messages = []

    async def accept(self):
        self.accepted = True

    async def send_json(
        self,
        payload,
    ):
        self.sent_messages.append(
            payload
        )


def build_pipeline():
    event_bus = DashboardEventBusV2()

    refresh_service = DashboardRefreshServiceV2(
        live_data_service_v2=(
            FakeLiveDataService()
        ),
        widget_registry_v2=(
            FakeWidgetRegistry()
        ),
    )

    websocket_hub = (
        DashboardWebSocketHubV2()
    )

    websocket_broadcaster = (
        DashboardWebSocketBroadcasterV2(
            refresh_service_v2=(
                refresh_service
            ),
            websocket_hub_v2=(
                websocket_hub
            ),
        )
    )

    dispatcher = DashboardEventDispatcherV2(
        event_bus_v2=event_bus,
        refresh_service_v2=(
            refresh_service
        ),
        websocket_broadcaster_v2=(
            websocket_broadcaster
        ),
    )

    auto_refresh_engine = (
        DashboardAutoRefreshEngineV2(
            event_bus_v2=event_bus,
            event_dispatcher_v2=(
                dispatcher
            ),
            refresh_service_v2=(
                refresh_service
            ),
        )
    )

    return {
        "event_bus": event_bus,
        "refresh_service": refresh_service,
        "websocket_hub": websocket_hub,
        "dispatcher": dispatcher,
        "auto_refresh_engine": (
            auto_refresh_engine
        ),
    }


@pytest.mark.parametrize(
    "event_type",
    [
        "trade_opened",
        "position_updated",
        "trade_closed",
        "risk_updated",
        "portfolio_updated",
    ],
)
def test_realtime_pipeline_end_to_end(
    event_type,
):
    pipeline = build_pipeline()

    start_result = (
        pipeline[
            "auto_refresh_engine"
        ].start()
    )

    assert start_result["started"] is True
    assert (
        start_result["subscription_count"]
        == 6
    )

    websocket = FakeWebSocket()

    asyncio.run(
        pipeline[
            "websocket_hub"
        ].connect(
            websocket=websocket,
        )
    )

    assert websocket.accepted is True

    publish_result = (
        pipeline[
            "auto_refresh_engine"
        ].publish_event(
            event_type=event_type,
            payload={
                "position_id": "pos-1",
                "symbol": "NQ",
            },
        )
    )

    assert publish_result["published"] is True
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

    refresh_state = (
        pipeline[
            "refresh_service"
        ].get_state()
    )

    assert refresh_state["refresh_count"] == 2
    assert (
        refresh_state["last_reason"]
        == event_type
    )

    assert len(
        websocket.sent_messages
    ) == 1

    message = websocket.sent_messages[0]

    assert (
        message["event_type"]
        == "dashboard_updated"
    )
    assert message["reason"] == event_type

    assert (
        message["source_event"][
            "event_type"
        ]
        == event_type
    )

    assert (
        message["dashboard"][
            "dashboard_status"
        ]
        == "READY"
    )

    assert (
        message["widgets"][
            "widget_count"
        ]
        == 1
    )

    hub_state = (
        pipeline[
            "websocket_hub"
        ].get_state()
    )

    assert hub_state["messages_sent"] == 1
    assert hub_state["send_errors"] == 0
