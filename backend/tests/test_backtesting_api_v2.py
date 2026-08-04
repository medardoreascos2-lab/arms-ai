from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.backtesting_api_v2 import (
    create_backtesting_router_v2,
)


class FakeResult:

    def to_dict(self):

        return {
            "backtest": {
                "total_candles": 2,
            },
            "backtest_score": {
                "score": 94.5,
                "grade": "A+",
            },
            "certification": {
                "status": "CERTIFIED",
            },
            "institutional_report": {
                "executive_summary": {
                    "status": "CERTIFIED",
                },
            },
        }


class FakeOrchestrator:

    def __init__(self):

        self.candles_received = None
        self.output_directory_received = None

    def run(
        self,
        *,
        candles,
        output_directory,
    ):

        self.candles_received = candles
        self.output_directory_received = output_directory

        return FakeResult()


def build_client():

    orchestrator = FakeOrchestrator()

    app = FastAPI()

    app.include_router(
        create_backtesting_router_v2(
            orchestrator=orchestrator,
        )
    )

    return (
        TestClient(app),
        orchestrator,
    )


def payload():

    return {
        "candles":[
            {
                "symbol":"NQ",
                "timeframe":"5m",
                "timestamp":"2026-08-04T09:30:00Z",
                "open":21000,
                "high":21010,
                "low":20995,
                "close":21005,
                "volume":1000,
            },
            {
                "symbol":"NQ",
                "timeframe":"5m",
                "timestamp":"2026-08-04T09:35:00Z",
                "open":21005,
                "high":21020,
                "low":21000,
                "close":21015,
                "volume":1100,
            },
        ],
        "output_directory":"reports/test",
    }


def test_run_backtesting():

    client, orchestrator = build_client()

    response = client.post(
        "/api/v2/backtesting/run",
        json=payload(),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["backtest"]["total_candles"] == 2
    assert body["backtest_score"]["score"] == 94.5
    assert body["certification"]["status"] == "CERTIFIED"

    assert len(
        orchestrator.candles_received
    ) == 2

    assert (
        orchestrator.output_directory_received
        == "reports/test"
    )


def test_router_requires_run():

    class Invalid:

        pass

    app = FastAPI()

    try:

        app.include_router(
            create_backtesting_router_v2(
                orchestrator=Invalid(),
            )
        )

        assert False

    except TypeError:

        pass
