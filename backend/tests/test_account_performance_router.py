from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.services.trade_history_store import (
    TradeHistoryStore,
)


def build_trade(
    *,
    index: int,
    pnl: float,
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
        "symbol": "NQ",
        "timeframe": "5m",
        "side": (
            "LONG"
            if index % 2 == 0
            else "SHORT"
        ),
        "status": "CLOSED",
        "closed": True,
        "entry_price": 21691.0 + index,
        "exit_price": 21695.0 + index,
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


def test_account_performance_endpoint():
    history_store = TradeHistoryStore()

    history_store.append(
        build_trade(
            index=0,
            pnl=150.0,
        )
    )

    history_store.append(
        build_trade(
            index=1,
            pnl=-75.0,
        )
    )

    history_store.append(
        build_trade(
            index=2,
            pnl=100.0,
        )
    )

    client = TestClient(
        create_app(
            trade_history_store=history_store
        )
    )

    response = client.get(
        "/market/performance",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
            "starting_balance": 17000.0,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["starting_balance"] == 17000.0
    assert body["current_balance"] == 17175.0
    assert body["realized_pnl"] == 175.0
    assert body["total_trades"] == 3
    assert body["winning_trades"] == 2
    assert body["losing_trades"] == 1
    assert body["win_rate"] == pytest.approx(
        66.6666666667
    )


def test_account_performance_empty_history():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/performance",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
            "starting_balance": 17000.0,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["current_balance"] == 17000.0
    assert body["realized_pnl"] == 0.0
    assert body["total_trades"] == 0


def test_account_performance_rejects_invalid_balance():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/performance",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
            "starting_balance": 0,
        },
    )

    assert response.status_code == 422


def test_account_performance_requires_symbol():
    client = TestClient(
        create_app()
    )

    response = client.get(
        "/market/performance",
        params={
            "timeframe": "5m",
            "starting_balance": 17000.0,
        },
    )

    assert response.status_code == 422
