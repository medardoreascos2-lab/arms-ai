from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_market_analysis_returns_200(
    monkeypatch,
):
    monkeypatch.setattr(
        "backend.api.routers.portfolio.download_prices",
        lambda symbols, period: __import__(
            "pandas"
        ).DataFrame(
            {
                "AAPL": [
                    100.0,
                    101.0,
                    103.0,
                    104.0,
                ],
                "MSFT": [
                    200.0,
                    202.0,
                    204.0,
                    208.0,
                ],
            }
        ),
    )

    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/from-market",
        json={
            "symbols": [
                "AAPL",
                "MSFT",
            ],
            "period": "1y",
            "risk_free_rate": 0.02,
        },
    )

    assert response.status_code == 200


def test_market_analysis_returns_strategy(
    monkeypatch,
):
    monkeypatch.setattr(
        "backend.api.routers.portfolio.download_prices",
        lambda symbols, period: __import__(
            "pandas"
        ).DataFrame(
            {
                "AAPL": [
                    100.0,
                    101.0,
                    103.0,
                    104.0,
                ],
                "MSFT": [
                    200.0,
                    202.0,
                    204.0,
                    208.0,
                ],
            }
        ),
    )

    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/from-market",
        json={
            "symbols": [
                "AAPL",
                "MSFT",
            ],
        },
    )

    payload = response.json()

    assert payload["strategy"]
    assert payload["risk_level"]
    assert set(
        payload["target_weights"]
    ) == {
        "AAPL",
        "MSFT",
    }


def test_market_analysis_rejects_empty_symbols():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/from-market",
        json={
            "symbols": [],
        },
    )

    assert response.status_code == 422
