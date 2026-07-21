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
            "IWM": [
                180.0,
                182.0,
                181.0,
                184.0,
                183.0,
            ],
            "IWD": [
                150.0,
                151.0,
                150.5,
                152.0,
                153.0,
            ],
            "IWF": [
                160.0,
                162.0,
                161.0,
                164.0,
                165.0,
            ],
        }
    )


def test_fama_french_analytics_from_market(
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
        "/portfolio/fama-french-analytics",
        json={
            "symbols": [
                "AAPL",
                "MSFT",
            ],
            "weights": {
                "AAPL": 0.6,
                "MSFT": 0.4,
            },
            "market": "SPY",
            "small_cap": "IWM",
            "value": "IWD",
            "growth": "IWF",
            "period": "1y",
            "risk_free_rate": 0.02,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "alpha" in body
    assert "beta_market" in body
    assert "beta_smb" in body
    assert "beta_hml" in body
    assert "r_squared" in body
    assert "expected_return" in body


def test_fama_french_rejects_empty_symbols():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/fama-french-analytics",
        json={
            "symbols": [],
            "weights": {},
        },
    )

    assert response.status_code == 422
