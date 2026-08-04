from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.backtesting_dashboard_api_v2 import (
    create_backtesting_dashboard_router_v2,
)


class FakeController:

    def status(self):

        return {
            "is_running": True,
            "registered_jobs": 12,
            "pending_tasks": 2,
            "iterations": 48,
            "last_error": None,
        }


def build_client():

    app = FastAPI()

    app.include_router(
        create_backtesting_dashboard_router_v2(
            controller=FakeController(),
        )
    )

    return TestClient(app)


def test_dashboard_summary():

    client = build_client()

    response = client.get(
        "/api/v2/backtesting/dashboard"
    )

    assert response.status_code == 200

    assert response.json() == {
        "controller": {
            "is_running": True,
            "registered_jobs": 12,
            "pending_tasks": 2,
            "iterations": 48,
            "last_error": None,
        }
    }


def test_invalid_controller():

    try:
        create_backtesting_dashboard_router_v2(
            controller=object(),
        )
    except TypeError as exc:
        assert "controller" in str(exc)
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )
