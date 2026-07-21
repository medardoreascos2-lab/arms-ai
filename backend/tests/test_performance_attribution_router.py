from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_performance_attribution_endpoint():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/performance-attribution",
        json={
            "portfolio_weights": {
                "AAPL": 0.40,
                "MSFT": 0.35,
                "NVDA": 0.25,
            },
            "benchmark_weights": {
                "AAPL": 0.30,
                "MSFT": 0.40,
                "NVDA": 0.30,
            },
            "portfolio_returns": {
                "AAPL": 0.18,
                "MSFT": 0.12,
                "NVDA": 0.30,
            },
            "benchmark_returns": {
                "AAPL": 0.15,
                "MSFT": 0.11,
                "NVDA": 0.22,
            },
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "portfolio_return" in body
    assert "benchmark_return" in body
    assert "active_return" in body
    assert "allocation_effect" in body
    assert "selection_effect" in body
    assert "interaction_effect" in body
    assert "asset_contributions" in body
    assert "best_asset" in body
    assert "worst_asset" in body


def test_performance_attribution_rejects_invalid_weights():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/performance-attribution",
        json={
            "portfolio_weights": {
                "AAPL": 0.20,
                "MSFT": 0.20,
            },
            "benchmark_weights": {
                "AAPL": 0.50,
                "MSFT": 0.50,
            },
            "portfolio_returns": {
                "AAPL": 0.10,
                "MSFT": 0.20,
            },
            "benchmark_returns": {
                "AAPL": 0.10,
                "MSFT": 0.20,
            },
        },
    )

    assert response.status_code == 400
