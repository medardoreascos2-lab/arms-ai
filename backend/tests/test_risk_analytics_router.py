from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_risk_analytics_endpoint():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/risk-analytics",
        json={
            "returns": [
                0.01,
                -0.02,
                0.015,
                -0.01,
                0.02,
                -0.03,
                0.01,
                0.005,
            ],
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


def test_risk_analytics_rejects_empty_returns():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/risk-analytics",
        json={
            "returns": [],
        },
    )

    assert response.status_code == 422
