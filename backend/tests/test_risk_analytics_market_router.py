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
        }
    )


def test_market_risk_analytics_returns_metrics(
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
        "/portfolio/risk-analytics-from-market",
        json={
            "symbols": [
                "AAPL",
                "MSFT",
            ],
            "weights": {
                "AAPL": 0.6,
                "MSFT": 0.4,
            },
            "period": "1y",
            "risk_free_rate": 0.02,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "annualized_return" in body
    assert "annualized_volatility" in body
    assert "sharpe_ratio" in body
    assert "sortino_ratio" in body
    assert "maximum_drawdown" in body
    assert "calmar_ratio" in body
    assert "value_at_risk_95" in body
    assert (
        "conditional_value_at_risk_95"
        in body
    )


def test_market_risk_analytics_rejects_empty_symbols():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/risk-analytics-from-market",
        json={
            "symbols": [],
            "weights": {},
        },
    )

    assert response.status_code == 422
