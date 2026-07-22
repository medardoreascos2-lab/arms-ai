from datetime import (
    datetime,
    timezone,
)

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.services.live_analysis_store import (
    LiveAnalysisStore,
)


def build_analysis() -> dict[str, object]:
    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "current_price": 21691.0,
        "trend": "ALCISTA",
        "indicators": {
            "ema": 21654.25,
            "ema_period": 50,
            "rsi": 57.4,
            "rsi_status": "NEUTRAL",
            "atr": 6.0,
            "atr_status": "ADECUADO",
        },
        "market_structure": {
            "direction": "ALCISTA",
            "high_type": "HH",
            "low_type": "HL",
        },
        "smart_money": {
            "bos": {
                "detected": True,
                "direction": "ALCISTA",
            },
            "choch": {
                "detected": False,
                "direction": "NINGUNA",
            },
            "liquidity": {
                "detected": True,
                "direction": "ALCISTA",
                "level": 21650.0,
                "equal_highs": False,
                "equal_lows": True,
            },
        },
        "decision": {
            "score": 87.0,
            "grade": "A+",
            "action": "BUY",
            "direction": "BUY",
            "approved": True,
            "confirmations": [],
            "warnings": [],
        },
        "probability": {
            "value": 84.0,
            "confidence": "MUY ALTA",
            "approved": True,
            "recommendation": "BUY",
            "positive_factors": [],
            "negative_factors": [],
        },
        "risk": {
            "approved": True,
            "risk_amount": 85.0,
            "stop_distance": 18.75,
            "take_profit_distance": 37.5,
            "contracts": 2,
        },
        "trade": {
            "entry_price": 21691.0,
            "stop_loss": 21672.25,
            "take_profit": 21728.5,
        },
        "analyzed_at": datetime(
            2026,
            7,
            22,
            19,
            30,
            tzinfo=timezone.utc,
        ),
    }


def test_latest_market_analysis_endpoint():
    store = LiveAnalysisStore()
    store.save(
        build_analysis()
    )

    client = TestClient(
        create_app(
            live_analysis_store=store
        )
    )

    response = client.get(
        "/market/latest-analysis",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["symbol"] == "NQ"
    assert body["timeframe"] == "5m"
    assert body["current_price"] == 21691.0
    assert body["decision"]["score"] == 87.0
    assert body["probability"]["value"] == 84.0


def test_latest_market_analysis_returns_404_when_missing():
    store = LiveAnalysisStore()

    client = TestClient(
        create_app(
            live_analysis_store=store
        )
    )

    response = client.get(
        "/market/latest-analysis",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
        },
    )

    assert response.status_code == 404


def test_latest_market_analysis_requires_symbol():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/latest-analysis",
        params={
            "timeframe": "5m",
        },
    )

    assert response.status_code == 422


def test_latest_market_analysis_requires_timeframe():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/latest-analysis",
        params={
            "symbol": "NQ",
        },
    )

    assert response.status_code == 422
