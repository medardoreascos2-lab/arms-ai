import numpy as np
from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_efficient_frontier_endpoint(monkeypatch):
    def fake_generate(**kwargs):
        return [
            {
                "expected_return": 0.10,
                "volatility": 0.20,
                "weights": {
                    "AAPL": 0.5,
                    "MSFT": 0.5,
                },
            }
        ]

    monkeypatch.setattr(
        "backend.api.routers.portfolio.EfficientFrontier.generate",
        fake_generate,
    )

    client = TestClient(create_app())

    response = client.post(
        "/portfolio/efficient-frontier",
        json={
            "returns": {
                "AAPL": [0.01, 0.02],
                "MSFT": [0.03, 0.01],
            },
            "volatilities": {
                "AAPL": 0.20,
                "MSFT": 0.15,
            },
            "expected_returns": {
                "AAPL": 0.10,
                "MSFT": 0.15,
            },
        },
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
