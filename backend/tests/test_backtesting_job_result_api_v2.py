from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.backtesting_jobs_api_v2 import (
    create_backtesting_jobs_router_v2,
)
from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)


class FakeResult:

    def __init__(self):

        self.report_directory = (
            "reports/job-001"
        )

    def to_dict(self):

        return {
            "report_directory": (
                self.report_directory
            ),
            "total_trades": 12,
            "net_profit": 850.0,
        }


class FakeResultProvider:

    def __init__(self):

        self.results = {
            "job-001": FakeResult(),
        }

    def get_result(
        self,
        job_id,
    ):

        return self.results.get(
            job_id
        )


def build_client():

    manager = BacktestingJobManagerV2()

    manager.create_job(
        job_id="job-001",
    )

    result_provider = (
        FakeResultProvider()
    )

    app = FastAPI()

    app.include_router(
        create_backtesting_jobs_router_v2(
            job_manager=manager,
            result_provider=(
                result_provider
            ),
        )
    )

    return (
        TestClient(app),
        result_provider,
    )


def test_get_result():

    client, _ = build_client()

    response = client.get(
        "/api/v2/backtesting/jobs/"
        "job-001/result"
    )

    assert response.status_code == 200

    assert response.json() == {
        "job_id": "job-001",
        "result": {
            "report_directory": (
                "reports/job-001"
            ),
            "total_trades": 12,
            "net_profit": 850.0,
        },
    }


def test_unknown_result_returns_404():

    client, _ = build_client()

    response = client.get(
        "/api/v2/backtesting/jobs/"
        "unknown/result"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "backtesting_result_not_found"
    )


def test_result_provider_not_configured():

    manager = BacktestingJobManagerV2()

    app = FastAPI()

    app.include_router(
        create_backtesting_jobs_router_v2(
            job_manager=manager,
        )
    )

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/jobs/"
        "job-001/result"
    )

    assert response.status_code == 503

    assert response.json()["detail"] == (
        "backtesting_result_provider_"
        "not_configured"
    )


def test_invalid_result_provider():

    manager = BacktestingJobManagerV2()

    try:
        create_backtesting_jobs_router_v2(
            job_manager=manager,
            result_provider=object(),
        )
    except TypeError as exc:
        assert "result_provider" in str(exc)
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )
