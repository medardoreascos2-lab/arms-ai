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
            "NVDA": [
                300.0,
                306.0,
                297.0,
                315.0,
                312.0,
            ],
        }
    )


def test_risk_contribution_from_market(
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
        "/portfolio/risk-contribution",
        json={
            "symbols": [
                "AAPL",
                "MSFT",
                "NVDA",
            ],
            "weights": {
                "AAPL": 0.40,
                "MSFT": 0.35,
                "NVDA": 0.25,
            },
            "period": "1y",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "portfolio_volatility" in body
    assert "marginal_contributions" in body
    assert "absolute_contributions" in body
    assert "percentage_contributions" in body
    assert "highest_risk_asset" in body
    assert "lowest_risk_asset" in body


def test_risk_contribution_rejects_empty_symbols():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/risk-contribution",
        json={
            "symbols": [],
            "weights": {},
        },
    )

    assert response.status_code == 422
