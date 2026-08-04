from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.backtesting_dashboard_api_v2 import (
    create_backtesting_dashboard_router_v2,
)


class FakeController:

    def status(self):

        return {
            "is_running": True,
            "registered_jobs": 3,
            "pending_tasks": 2,
            "iterations": 15,
            "last_error": None,
        }


class FakeQueue:

    def __len__(self):

        return 2


class FakeWorker:

    def status(self):

        return {
            "is_running": False,
            "iterations": 15,
            "last_error": None,
        }


def build_client():

    app = FastAPI()

    app.include_router(
        create_backtesting_dashboard_router_v2(
            controller=FakeController(),
            job_queue=FakeQueue(),
            worker=FakeWorker(),
        )
    )

    return TestClient(app)


def test_dashboard_includes_queue_and_worker():

    client = build_client()

    response = client.get(
        "/api/v2/backtesting/dashboard"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["queue"] == {
        "pending_tasks": 2,
    }

    assert payload["worker"] == {
        "is_running": False,
        "iterations": 15,
        "last_error": None,
    }


def test_invalid_worker():

    try:
        create_backtesting_dashboard_router_v2(
            controller=FakeController(),
            worker=object(),
        )
    except TypeError as exc:
        assert "worker" in str(exc)
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )


def test_invalid_queue():

    try:
        create_backtesting_dashboard_router_v2(
            controller=FakeController(),
            job_queue=object(),
        )
    except TypeError as exc:
        assert "job_queue" in str(exc)
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )
