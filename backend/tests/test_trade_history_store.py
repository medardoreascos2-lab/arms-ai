from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.services.trade_history_store import (
    TradeHistoryStore,
)


def build_closed_trade(
    *,
    index: int = 0,
    symbol: str = "NQ",
    timeframe: str = "5m",
    side: str = "LONG",
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

    closed_at = (
        opened_at
        + timedelta(
            minutes=30 + index
        )
    )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "side": side,
        "status": "CLOSED",
        "closed": True,
        "entry_price": 21691.0 + index,
        "exit_price": 21728.5 + index,
        "stop_loss": 21672.25 + index,
        "take_profit": 21728.5 + index,
        "contracts": 2,
        "opened_at": opened_at,
        "closed_at": closed_at,
        "close_reason": "TAKE_PROFIT",
        "pnl_points": 37.5,
        "pnl": pnl,
    }


def test_appends_and_returns_trade_history():
    store = TradeHistoryStore()

    for index in range(3):
        store.append(
            build_closed_trade(
                index=index
            )
        )

    result = store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(result) == 3
    assert (
        result[0]["closed_at"]
        < result[1]["closed_at"]
        < result[2]["closed_at"]
    )


def test_returns_latest_requested_trades():
    store = TradeHistoryStore()

    for index in range(5):
        store.append(
            build_closed_trade(
                index=index
            )
        )

    result = store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=2,
    )

    assert len(result) == 2
    assert result[0]["entry_price"] == 21694.0
    assert result[1]["entry_price"] == 21695.0


def test_keeps_markets_separated():
    store = TradeHistoryStore()

    store.append(
        build_closed_trade(
            symbol="NQ",
            timeframe="5m",
        )
    )

    store.append(
        build_closed_trade(
            symbol="ES",
            timeframe="1m",
        )
    )

    nq = store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    es = store.get_history(
        symbol="ES",
        timeframe="1m",
        limit=10,
    )

    assert len(nq) == 1
    assert len(es) == 1
    assert nq[0]["symbol"] == "NQ"
    assert es[0]["symbol"] == "ES"


def test_replaces_duplicate_closed_at():
    store = TradeHistoryStore()

    original = build_closed_trade(
        index=0,
        pnl=150.0,
    )

    replacement = {
        **build_closed_trade(
            index=0,
            pnl=200.0,
        ),
        "close_reason": "MANUAL",
    }

    store.append(original)
    store.append(replacement)

    result = store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(result) == 1
    assert result[0]["pnl"] == 200.0
    assert result[0]["close_reason"] == "MANUAL"


def test_limits_history_per_market():
    store = TradeHistoryStore(
        max_trades=3
    )

    for index in range(5):
        store.append(
            build_closed_trade(
                index=index
            )
        )

    result = store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(result) == 3
    assert result[0]["entry_price"] == 21693.0
    assert result[-1]["entry_price"] == 21695.0


def test_returns_defensive_copies():
    store = TradeHistoryStore()

    store.append(
        build_closed_trade()
    )

    first = store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    first[0]["pnl"] = -999.0

    second = store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert second[0]["pnl"] == 150.0


def test_rejects_open_trade():
    store = TradeHistoryStore()

    trade = build_closed_trade()
    trade["status"] = "OPEN"
    trade["closed"] = False

    with pytest.raises(
        ValueError,
        match="CLOSED",
    ):
        store.append(trade)


def test_rejects_invalid_limit():
    store = TradeHistoryStore()

    with pytest.raises(
        ValueError,
        match="limit",
    ):
        store.get_history(
            symbol="NQ",
            timeframe="5m",
            limit=0,
        )


def test_rejects_invalid_max_trades():
    with pytest.raises(
        ValueError,
        match="max_trades",
    ):
        TradeHistoryStore(
            max_trades=0
        )
