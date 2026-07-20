import pandas as pd
from fastapi.testclient import TestClient

from backend.api.app import create_app


def build_prices() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "AAPL": [
                100.0,
                102.0,
                101.0,
                105.0,
                104.0,
            ],
            "MSFT": [
                200.0,
                204.0,
                208.0,
                206.0,
                210.0,
            ],
            "SPY": [
                400.0,
                404.0,
                402.0,
                408.0,
                410.0,
            ],
        }
    )


def test_benchmark_analytics_from_market(
    monkeypatch,
):
    monkeypatch.setattr(
        "backend.api.routers.portfolio.download_prices",
        lambda symbols, period: build_prices(),
    )

    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/benchmark-analytics",
        json={
            "symbols": [
                "AAPL",
                "MSFT",
            ],
            "weights": {
                "AAPL": 0.6,
                "MSFT": 0.4,
            },
            "benchmark": "SPY",
            "period": "1y",
            "risk_free_rate": 0.02,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "beta" in body
    assert "alpha" in body
    assert "tracking_error" in body
    assert "information_ratio" in body
    assert "portfolio_curve" in body
    assert "benchmark_curve" in body


def test_benchmark_analytics_rejects_empty_symbols():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/benchmark-analytics",
        json={
            "symbols": [],
            "weights": {},
            "benchmark": "SPY",
        },
    )

    assert response.status_code == 422
