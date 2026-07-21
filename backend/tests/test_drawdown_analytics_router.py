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


def test_drawdown_analytics_from_market(
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
        "/portfolio/drawdown-analytics",
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
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "equity_curve" in body
    assert "drawdown_curve" in body
    assert "maximum_drawdown" in body
    assert "maximum_drawdown_duration" in body
    assert "peak_index" in body
    assert "trough_index" in body


def test_drawdown_analytics_rejects_empty_symbols():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/drawdown-analytics",
        json={
            "symbols": [],
            "weights": {},
        },
    )

    assert response.status_code == 422
