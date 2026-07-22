from datetime import (
    datetime,
    timedelta,
    timezone,
)

from fastapi.testclient import TestClient

from backend.api.app import create_app


def build_candles(
    total: int = 60,
) -> list[dict[str, object]]:
    start = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone.utc,
    )

    candles = []

    for index in range(total):
        base = 21600.0 + index * 1.5

        candles.append(
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "open": base,
                "high": base + 4.0,
                "low": base - 2.0,
                "close": base + 2.5,
                "volume": 1000.0 + index * 10,
                "timestamp": (
                    start
                    + timedelta(
                        minutes=index * 5
                    )
                ).isoformat(),
            }
        )

    return candles


def build_payload() -> dict[str, object]:
    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "candles": build_candles(),
        "account_balance": 17000.0,
        "risk_percent": 0.5,
        "point_value": 2.0,
        "reward_risk_ratio": 2.0,
    }


def test_ai_trading_context_endpoint():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/ai/trading-context",
        json=build_payload(),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["symbol"] == "NQ"
    assert body["timeframe"] == "5m"

    assert "current_price" in body
    assert "trend" in body
    assert "indicators" in body
    assert "market_structure" in body
    assert "smart_money" in body
    assert "decision" in body
    assert "probability" in body
    assert "risk" in body
    assert "trade" in body


def test_ai_trading_context_returns_decision_data():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/ai/trading-context",
        json=build_payload(),
    )

    assert response.status_code == 200

    body = response.json()

    assert "score" in body["decision"]
    assert "grade" in body["decision"]
    assert "action" in body["decision"]
    assert "approved" in body["decision"]

    assert "value" in body["probability"]
    assert "confidence" in body["probability"]
    assert "approved" in body["probability"]


def test_ai_trading_context_rejects_empty_candles():
    client = TestClient(
        create_app()
    )

    payload = build_payload()
    payload["candles"] = []

    response = client.post(
        "/ai/trading-context",
        json=payload,
    )

    assert response.status_code == 422


def test_ai_trading_context_rejects_too_few_candles():
    client = TestClient(
        create_app()
    )

    payload = build_payload()
    payload["candles"] = build_candles(
        total=20
    )

    response = client.post(
        "/ai/trading-context",
        json=payload,
    )

    assert response.status_code == 422


def test_ai_trading_context_rejects_invalid_risk():
    client = TestClient(
        create_app()
    )

    payload = build_payload()
    payload["risk_percent"] = 0

    response = client.post(
        "/ai/trading-context",
        json=payload,
    )

    assert response.status_code == 422
