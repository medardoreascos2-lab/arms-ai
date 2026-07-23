from datetime import (
    datetime,
    timedelta,
    timezone,
)

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.services.trade_history_store import (
    TradeHistoryStore,
)


def build_trade(
    *,
    index: int,
    symbol: str = "NQ",
    timeframe: str = "5m",
    pnl: float = 150.0,
) -> dict[str, object]:
    opened_at = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone.utc,
    )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "side": (
            "LONG"
            if index % 2 == 0
            else "SHORT"
        ),
        "status": "CLOSED",
        "closed": True,
        "entry_price": 21691.0 + index,
        "exit_price": 21700.0 + index,
        "stop_loss": 21672.25,
        "take_profit": 21728.50,
        "contracts": 2,
        "opened_at": opened_at,
        "closed_at": (
            opened_at
            + timedelta(
                minutes=30 + index
            )
        ),
        "close_reason": "MANUAL",
        "pnl_points": pnl / 4.0,
        "pnl": pnl,
    }


def test_returns_trade_history():
    store = TradeHistoryStore()

    for index in range(3):
        store.append(
            build_trade(
                index=index
            )
        )

    client = TestClient(
        create_app(
            trade_history_store=store
        )
    )

    response = client.get(
        "/market/trades",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
            "limit": 10,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["symbol"] == "NQ"
    assert body["timeframe"] == "5m"
    assert body["count"] == 3
    assert len(body["trades"]) == 3
    assert body["trades"][0]["entry_price"] == 21691.0
    assert body["trades"][-1]["entry_price"] == 21693.0


def test_respects_trade_history_limit():
    store = TradeHistoryStore()

    for index in range(5):
        store.append(
            build_trade(
                index=index
            )
        )

    client = TestClient(
        create_app(
            trade_history_store=store
        )
    )

    response = client.get(
        "/market/trades",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
            "limit": 2,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["count"] == 2
    assert body["trades"][0]["entry_price"] == 21694.0
    assert body["trades"][1]["entry_price"] == 21695.0


def test_returns_empty_trade_history():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/trades",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
            "limit": 10,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["count"] == 0
    assert body["trades"] == []


def test_rejects_invalid_trade_limit():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/trades",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
            "limit": 0,
        },
    )

    assert response.status_code == 422


def test_trade_history_requires_symbol():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/trades",
        params={
            "timeframe": "5m",
            "limit": 10,
        },
    )

    assert response.status_code == 422


def test_trade_history_requires_timeframe():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/trades",
        params={
            "symbol": "NQ",
            "limit": 10,
        },
    )

    assert response.status_code == 422
