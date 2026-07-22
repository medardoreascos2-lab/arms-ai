from fastapi.testclient import TestClient

from backend.api.app import create_app


def build_payload() -> dict[str, object]:
    return {
        "question": "Analiza mi portafolio.",
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


def test_ai_copilot_endpoint():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/ai/copilot",
        json=build_payload(),
    )

    assert response.status_code == 200

    body = response.json()

    assert "provider" in body
    assert "model" in body
    assert "content" in body
    assert "decision" in body


def test_ai_copilot_returns_decision_context():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/ai/copilot",
        json=build_payload(),
    )

    assert response.status_code == 200

    decision = response.json()[
        "decision"
    ]

    assert "score" in decision
    assert "risk_level" in decision
    assert "recommendations" in decision
    assert "alerts" in decision


def test_ai_copilot_rejects_empty_question():
    client = TestClient(
        create_app()
    )

    payload = build_payload()
    payload["question"] = ""

    response = client.post(
        "/ai/copilot",
        json=payload,
    )

    assert response.status_code == 400


def test_ai_copilot_rejects_invalid_weights():
    client = TestClient(
        create_app()
    )

    payload = build_payload()
    payload["weights"] = {
        "AAPL": 0.20,
        "MSFT": 0.20,
    }

    response = client.post(
        "/ai/copilot",
        json=payload,
    )

    assert response.status_code == 400


def test_ai_copilot_rejects_missing_metric():
    client = TestClient(
        create_app()
    )

    payload = build_payload()
    payload["metrics"] = {
        "volatility": 0.22,
        "sharpe_ratio": 0.75,
        "beta": 1.20,
    }

    response = client.post(
        "/ai/copilot",
        json=payload,
    )

    assert response.status_code == 400
