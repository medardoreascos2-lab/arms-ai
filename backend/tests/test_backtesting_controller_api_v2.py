from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.backtesting_controller_api_v2 import (
    create_backtesting_controller_router_v2,
)


class FakeController:

    def __init__(self):

        self.start_calls = 0
        self.stop_calls = 0
        self.is_running = False

    def start(self):

        self.start_calls += 1
        self.is_running = True

        return object()

    def stop(
        self,
        *,
        timeout=None,
    ):

        self.stop_calls += 1
        self.is_running = False

    def status(self):

        return {
            "is_running": self.is_running,
            "registered_jobs": 2,
            "pending_tasks": 1,
            "iterations": 5,
            "last_error": None,
        }


def build_client():

    controller = FakeController()

    app = FastAPI()

    app.include_router(
        create_backtesting_controller_router_v2(
            controller=controller,
        )
    )

    return (
        TestClient(app),
        controller,
    )


def test_status_endpoint():

    client, _ = build_client()

    response = client.get(
        "/api/v2/backtesting/controller/status"
    )

    assert response.status_code == 200

    assert response.json() == {
        "is_running": False,
        "registered_jobs": 2,
        "pending_tasks": 1,
        "iterations": 5,
        "last_error": None,
    }


def test_start_endpoint():

    client, controller = build_client()

    response = client.post(
        "/api/v2/backtesting/controller/start"
    )

    assert response.status_code == 200
    assert controller.start_calls == 1
    assert controller.is_running is True

    assert response.json() == {
        "started": True,
        "is_running": True,
    }


def test_stop_endpoint():

    client, controller = build_client()

    controller.start()

    response = client.post(
        "/api/v2/backtesting/controller/stop"
    )

    assert response.status_code == 200
    assert controller.stop_calls == 1
    assert controller.is_running is False

    assert response.json() == {
        "stopped": True,
        "is_running": False,
    }


def test_invalid_controller():

    try:
        create_backtesting_controller_router_v2(
            controller=object(),
        )
    except TypeError as exc:
        assert "controller" in str(exc)
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )
