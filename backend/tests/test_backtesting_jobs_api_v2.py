from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.backtesting_jobs_api_v2 import (
    create_backtesting_jobs_router_v2,
)
from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
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
        "output_directory": "reports/test",
    }


def build_client():

    manager = BacktestingJobManagerV2()

    app = FastAPI()

    app.include_router(
        create_backtesting_jobs_router_v2(
            job_manager=manager,
        )
    )

    return TestClient(app), manager


def test_create_job():

    client, _ = build_client()

    response = client.post(
        "/api/v2/backtesting/jobs",
        json=valid_payload(),
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["job_id"]
    assert payload["status"] == "PENDING"
    assert payload["progress"] == 0.0
    assert payload["task"]["candle_count"] == 1


def test_list_jobs():

    client, manager = build_client()

    manager.create_job()
    manager.create_job()

    response = client.get(
        "/api/v2/backtesting/jobs"
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_job():

    client, manager = build_client()

    job = manager.create_job()

    response = client.get(
        f"/api/v2/backtesting/jobs/{job.job_id}"
    )

    assert response.status_code == 200
    assert response.json()["job_id"] == job.job_id


def test_unknown_job_returns_404():

    client, _ = build_client()

    response = client.get(
        "/api/v2/backtesting/jobs/unknown"
    )

    assert response.status_code == 404


def test_delete_job():

    client, manager = build_client()

    job = manager.create_job()

    response = client.delete(
        f"/api/v2/backtesting/jobs/{job.job_id}"
    )

    assert response.status_code == 200
    assert manager.get_job(job.job_id) is None


def test_invalid_manager():

    try:
        create_backtesting_jobs_router_v2(
            job_manager=object(),
        )
    except TypeError as exc:
        assert "job_manager" in str(exc)
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )
