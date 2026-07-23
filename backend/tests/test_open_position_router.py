from datetime import (
    datetime,
    timezone,
)

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.execution.position_manager import (
    PositionManager,
)


def build_trade() -> dict[str, object]:
    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "action": "BUY",
        "entry_price": 21691.0,
        "stop_loss": 21672.25,
        "take_profit": 21728.50,
        "contracts": 2,
        "executed": True,
        "status": "SIMULATED",
        "mode": "SIMULATED",
        "executed_at": datetime(
            2026,
            7,
            22,
            9,
            30,
            tzinfo=timezone.utc,
        ),
    }


def test_returns_open_position():
    manager = PositionManager()

    manager.open_position(
        build_trade()
    )

    client = TestClient(
        create_app(
            position_manager=manager
        )
    )

    response = client.get(
        "/market/open-position",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["symbol"] == "NQ"
    assert body["timeframe"] == "5m"
    assert body["side"] == "LONG"
    assert body["status"] == "OPEN"
    assert body["entry_price"] == 21691.0
    assert body["contracts"] == 2


def test_returns_404_when_no_position():
    manager = PositionManager()

    client = TestClient(
        create_app(
            position_manager=manager
        )
    )

    response = client.get(
        "/market/open-position",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
        },
    )

    assert response.status_code == 404


def test_requires_symbol():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/open-position",
        params={
            "timeframe": "5m",
        },
    )

    assert response.status_code == 422


def test_requires_timeframe():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/open-position",
        params={
            "symbol": "NQ",
        },
    )

    assert response.status_code == 422
