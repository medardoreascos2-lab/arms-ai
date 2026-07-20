from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_backtest_endpoint(monkeypatch):
    def fake_run(self, **kwargs):
        return {
            "initial_value": 1000.0,
            "final_value": 1200.0,
            "equity_curve": [
                1000.0,
                1050.0,
                1100.0,
                1200.0,
            ],
            "total_return": 0.20,
            "annualized_return": 0.18,
            "annualized_volatility": 0.12,
            "sharpe_ratio": 1.5,
            "maximum_drawdown": -0.08,
        }

    monkeypatch.setattr(
        "backend.portfolio.portfolio_backtest.PortfolioBacktest.run",
        fake_run,
    )

    client = TestClient(create_app())

    response = client.post(
        "/portfolio/backtest",
        json={
            "symbols": [
                "AAPL",
                "MSFT",
            ],
            "weights": {
                "AAPL": 0.6,
                "MSFT": 0.4,
            },
            "initial_value": 1000,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["final_value"] == 1200.0
    assert len(body["equity_curve"]) == 4
