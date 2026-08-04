from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.backtesting_dashboard_api_v2 import (
    create_backtesting_dashboard_router_v2,
)
from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)


class FakeController:

    def status(self):

        return {
            "is_running": True,
            "registered_jobs": 4,
            "pending_tasks": 1,
            "iterations": 20,
            "last_error": None,
        }


def build_client():

    manager = BacktestingJobManagerV2()

    pending_job = manager.create_job(
        job_id="pending-job",
    )

    running_job = manager.create_job(
        job_id="running-job",
    )
    running_job.start()

    completed_job = manager.create_job(
        job_id="completed-job",
    )
    completed_job.start()
    completed_job.finish(
        report_directory=(
            "reports/completed-job"
        ),
    )

    failed_job = manager.create_job(
        job_id="failed-job",
    )
    failed_job.start()
    failed_job.fail(
        "execution_failed"
    )

    app = FastAPI()

    app.include_router(
        create_backtesting_dashboard_router_v2(
            controller=FakeController(),
            job_manager=manager,
        )
    )

    return (
        TestClient(app),
        pending_job,
        running_job,
        completed_job,
        failed_job,
    )


def test_dashboard_includes_job_counts():

    client, *_ = build_client()

    response = client.get(
        "/api/v2/backtesting/dashboard"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["jobs"] == {
        "registered": 4,
        "pending": 1,
        "running": 1,
        "completed": 1,
        "failed": 1,
    }


def test_dashboard_keeps_controller_summary():

    client, *_ = build_client()

    response = client.get(
        "/api/v2/backtesting/dashboard"
    )

    assert response.status_code == 200

    assert response.json()["controller"] == {
        "is_running": True,
        "registered_jobs": 4,
        "pending_tasks": 1,
        "iterations": 20,
        "last_error": None,
    }


def test_invalid_job_manager():

    try:
        create_backtesting_dashboard_router_v2(
            controller=FakeController(),
            job_manager=object(),
        )
    except TypeError as exc:
        assert "job_manager" in str(exc)
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )
