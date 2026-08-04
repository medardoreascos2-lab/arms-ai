from time import monotonic, sleep

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.backtesting.backtesting_job_v2 import (
    BacktestingJobStatusV2,
)


class FakeResult:

    def __init__(
        self,
        *,
        report_directory,
    ):

        self.report_directory = report_directory


class FakeOrchestrator:

    def __init__(self):

        self.calls = []

    def run(
        self,
        *,
        candles,
        output_directory,
    ):

        self.calls.append(
            {
                "candles": candles,
                "output_directory": (
                    output_directory
                ),
            }
        )

        return FakeResult(
            report_directory=(
                output_directory
            ),
        )


def valid_payload():

    return {
        "candles": [
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "timestamp": (
                    "2026-08-04T09:30:00Z"
                ),
                "open": 21000.0,
                "high": 21010.0,
                "low": 20995.0,
                "close": 21005.0,
                "volume": 1000.0,
            },
        ],
        "output_directory": (
            "reports/e2e-job"
        ),
    }


def wait_until(
    predicate,
    *,
    timeout=2.0,
):

    deadline = (
        monotonic()
        + timeout
    )

    while monotonic() < deadline:

        if predicate():
            return True

        sleep(0.01)

    return False


def test_controller_processes_job_end_to_end():

    orchestrator = FakeOrchestrator()

    app = create_app(
        backtesting_orchestrator_v2=(
            orchestrator
        ),
    )

    client = TestClient(app)

    create_response = client.post(
        "/api/v2/backtesting/jobs",
        json=valid_payload(),
    )

    assert create_response.status_code == 201

    job_id = (
        create_response
        .json()["job_id"]
    )

    job = (
        app.state
        .backtesting_job_manager_v2
        .get_job(job_id)
    )

    assert job is not None

    assert (
        job.status
        == BacktestingJobStatusV2.PENDING
    )

    assert len(
        app.state
        .backtesting_job_queue_v2
    ) == 1

    start_response = client.post(
        "/api/v2/backtesting/controller/start"
    )

    assert start_response.status_code == 200

    assert wait_until(
        lambda: (
            job.status
            == BacktestingJobStatusV2.COMPLETED
        ),
        timeout=2.0,
    )

    stop_response = client.post(
        "/api/v2/backtesting/controller/stop"
    )

    assert stop_response.status_code == 200

    assert len(orchestrator.calls) == 1

    assert (
        orchestrator.calls[0]
        ["output_directory"]
        == "reports/e2e-job"
    )

    assert len(
        orchestrator.calls[0]["candles"]
    ) == 1

    assert job.progress == 100.0

    assert (
        job.report_directory
        == "reports/e2e-job"
    )

    assert len(
        app.state
        .backtesting_job_queue_v2
    ) == 0


def test_controller_status_updates_after_execution():

    orchestrator = FakeOrchestrator()

    app = create_app(
        backtesting_orchestrator_v2=(
            orchestrator
        ),
    )

    client = TestClient(app)

    response = client.post(
        "/api/v2/backtesting/jobs",
        json=valid_payload(),
    )

    assert response.status_code == 201

    job_id = response.json()["job_id"]

    client.post(
        "/api/v2/backtesting/controller/start"
    )

    job = (
        app.state
        .backtesting_job_manager_v2
        .get_job(job_id)
    )

    assert wait_until(
        lambda: (
            job.status
            == BacktestingJobStatusV2.COMPLETED
        ),
        timeout=2.0,
    )

    status_response = client.get(
        "/api/v2/backtesting/controller/status"
    )

    client.post(
        "/api/v2/backtesting/controller/stop"
    )

    assert status_response.status_code == 200

    payload = status_response.json()

    assert payload["registered_jobs"] == 1
    assert payload["pending_tasks"] == 0
    assert payload["iterations"] >= 1
    assert payload["last_error"] is None
