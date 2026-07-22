from fastapi.testclient import TestClient

from backend.api.app import create_app


def build_payload() -> dict[str, object]:
    return {
        "weights": {
            "AAPL": 0.50,
            "MSFT": 0.30,
            "NVDA": 0.20,
        },
        "metrics": {
            "volatility": 0.22,
            "sharpe_ratio": 0.75,
            "beta": 1.20,
            "drawdown": -0.18,
        },
    }


def test_ai_decision_endpoint():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/ai/decision",
        json=build_payload(),
    )

    assert response.status_code == 200

    body = response.json()

    assert "score" in body
    assert "risk_level" in body
    assert "alerts" in body
    assert "recommendations" in body
    assert "explanations" in body
    assert "summary" in body


def test_ai_decision_includes_metric_explanations():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/ai/decision",
        json=build_payload(),
    )

    assert response.status_code == 200

    explanations = response.json()[
        "explanations"
    ]

    assert set(explanations) == {
        "volatility",
        "sharpe_ratio",
        "beta",
        "drawdown",
        "portfolio_score",
    }


def test_ai_decision_rejects_invalid_weight_sum():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/ai/decision",
        json={
            "weights": {
                "AAPL": 0.30,
                "MSFT": 0.20,
            },
            "metrics": {
                "volatility": 0.22,
                "sharpe_ratio": 0.75,
                "beta": 1.20,
                "drawdown": -0.18,
            },
        },
    )

    assert response.status_code == 400


def test_ai_decision_rejects_missing_metric():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/ai/decision",
        json={
            "weights": {
                "AAPL": 0.50,
                "MSFT": 0.50,
            },
            "metrics": {
                "volatility": 0.22,
                "sharpe_ratio": 0.75,
                "beta": 1.20,
            },
        },
    )

    assert response.status_code == 400


def test_ai_decision_rejects_empty_weights():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/ai/decision",
        json={
            "weights": {},
            "metrics": {
                "volatility": 0.22,
                "sharpe_ratio": 0.75,
                "beta": 1.20,
                "drawdown": -0.18,
            },
        },
    )

    assert response.status_code == 400
