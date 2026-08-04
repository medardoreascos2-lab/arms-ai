from time import monotonic, sleep

from fastapi.testclient import TestClient

from backend.api.app import create_app


class FakeResult:

    def __init__(
        self,
        *,
        report_directory,
    ):

        self.report_directory = report_directory

    def to_dict(
        self,
    ):

        return {
            "report_directory": (
                self.report_directory
            ),
        }


class FakeOrchestrator:

    def run(
        self,
        *,
        candles,
        output_directory,
    ):

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
            "reports/app-result"
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


def test_app_exposes_result_provider():

    app = create_app()

    assert hasattr(
        app.state,
        "backtesting_job_executor_v2",
    )


def test_result_endpoint_uses_shared_executor():

    app = create_app(
        backtesting_orchestrator_v2=(
            FakeOrchestrator()
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

    start_response = client.post(
        "/api/v2/backtesting/controller/start"
    )

    assert start_response.status_code == 200

    assert wait_until(
        lambda: (
            app.state
            .backtesting_job_executor_v2
            .get_result(job_id)
            is not None
        ),
        timeout=2.0,
    )

    result_response = client.get(
        f"/api/v2/backtesting/jobs/{job_id}/result"
    )

    client.post(
        "/api/v2/backtesting/controller/stop"
    )

    assert result_response.status_code == 200

    assert result_response.json() == {
        "job_id": job_id,
        "result": {
            "report_directory": (
                "reports/app-result"
            ),
        },
    }


def test_unknown_result_from_app_returns_404():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/jobs/"
        "unknown/result"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "backtesting_result_not_found"
    )
