from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.backtesting_metrics_api_v2 import (
    create_backtesting_metrics_router_v2,
)


class FakeMetricsProvider:

    def get_metrics(self):

        return {
            "total_trades": 120,
            "winning_trades": 78,
            "losing_trades": 42,
            "win_rate": 65.0,
            "profit_factor": 1.85,
            "net_profit": 4500.0,
            "max_drawdown": -900.0,
        }


def build_client():

    app = FastAPI()

    app.include_router(
        create_backtesting_metrics_router_v2(
            metrics_provider=(
                FakeMetricsProvider()
            ),
        )
    )

    return TestClient(app)


def test_get_backtesting_metrics():

    client = build_client()

    response = client.get(
        "/api/v2/backtesting/metrics"
    )

    assert response.status_code == 200

    assert response.json() == {
        "metrics": {
            "total_trades": 120,
            "winning_trades": 78,
            "losing_trades": 42,
            "win_rate": 65.0,
            "profit_factor": 1.85,
            "net_profit": 4500.0,
            "max_drawdown": -900.0,
        }
    }


def test_invalid_metrics_provider():

    try:
        create_backtesting_metrics_router_v2(
            metrics_provider=object(),
        )

    except TypeError as exc:

        assert "metrics_provider" in str(exc)

    else:

        raise AssertionError(
            "Se esperaba TypeError."
        )
