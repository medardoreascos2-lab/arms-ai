from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dashboard_websocket_api_v2 import (
    create_dashboard_websocket_router_v2,
)


class FakeWebSocketHub:

    def __init__(self):
        self.connected = []
        self.disconnected = []

    async def connect(
        self,
        *,
        websocket,
    ):
        await websocket.accept()

        self.connected.append(
            websocket
        )

        return {
            "connected": True,
            "connection_count": len(
                self.connected
            ),
        }

    def disconnect(
        self,
        *,
        websocket,
    ):
        self.disconnected.append(
            websocket
        )

        return {
            "disconnected": True,
            "connection_count": 0,
        }


class FakeLiveDataService:

    def get_snapshot(self):
        return {
            "snapshot_time": (
                "2026-07-26T03:00:00+00:00"
            ),
            "dashboard_status": "READY",
            "performance_score": {
                "score": 92,
                "grade": "A+",
            },
        }


def build_client(
    *,
    websocket_hub=None,
    live_data_service=None,
):
    app = FastAPI()

    router = (
        create_dashboard_websocket_router_v2(
            websocket_hub_v2=(
                websocket_hub
            ),
            live_data_service_v2=(
                live_data_service
            ),
        )
    )

    app.include_router(
        router
    )

    return TestClient(
        app
    )


def test_rejects_invalid_websocket_hub():
    try:
        create_dashboard_websocket_router_v2(
            websocket_hub_v2=object(),
            live_data_service_v2=None,
        )
    except TypeError as exc:
        assert (
            "websocket_hub_v2"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )


def test_rejects_invalid_live_data_service():
    try:
        create_dashboard_websocket_router_v2(
            websocket_hub_v2=None,
            live_data_service_v2=object(),
        )
    except TypeError as exc:
        assert (
            "live_data_service_v2"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )


def test_websocket_receives_initial_snapshot():
    hub = FakeWebSocketHub()

    client = build_client(
        websocket_hub=hub,
        live_data_service=(
            FakeLiveDataService()
        ),
    )

    with client.websocket_connect(
        "/api/v2/dashboard/ws"
    ) as websocket:

        payload = (
            websocket.receive_json()
        )

        assert (
            payload["event_type"]
            == "dashboard_snapshot"
        )

        assert (
            payload["data"][
                "dashboard_status"
            ]
            == "READY"
        )

        assert (
            payload["data"][
                "performance_score"
            ]["score"]
            == 92
        )

    assert len(hub.connected) == 1
    assert len(hub.disconnected) == 1


def test_websocket_without_live_data_service():
    hub = FakeWebSocketHub()

    client = build_client(
        websocket_hub=hub,
        live_data_service=None,
    )

    with client.websocket_connect(
        "/api/v2/dashboard/ws"
    ) as websocket:

        payload = (
            websocket.receive_json()
        )

        assert (
            payload["event_type"]
            == "dashboard_snapshot"
        )

        assert payload["data"] is None


def test_websocket_without_hub_closes():
    client = build_client(
        websocket_hub=None,
        live_data_service=(
            FakeLiveDataService()
        ),
    )

    try:
        with client.websocket_connect(
            "/api/v2/dashboard/ws"
        ):
            raise AssertionError(
                "La conexión debía cerrarse."
            )
    except Exception:
        pass
