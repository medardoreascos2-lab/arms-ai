import pytest

from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)


def build_manager() -> TradeHistoryManagerV2:
    return TradeHistoryManagerV2()


def build_closed_winning_position() -> dict[str, object]:
    return {
        "opened": True,
        "status": "CLOSED",
        "position_id": "position-001",
        "order_id": "order-001",
        "execution_mode": "PAPER",
        "symbol": "NQ",
        "direction": "LONG",
        "quantity": 2,
        "entry_price": 100.0,
        "current_price": 110.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "unrealized_points": 10.0,
        "unrealized_pnl": 40.0,
        "realized_pnl": 40.0,
        "exit_price": 110.0,
        "close_reason": "TAKE_PROFIT",
        "point_value": 2.0,
    }


def build_closed_losing_position() -> dict[str, object]:
    return {
        "opened": True,
        "status": "CLOSED",
        "position_id": "position-002",
        "order_id": "order-002",
        "execution_mode": "PAPER",
        "symbol": "NQ",
        "direction": "SHORT",
        "quantity": 1,
        "entry_price": 100.0,
        "current_price": 105.0,
        "stop_loss": 105.0,
        "take_profit": 90.0,
        "unrealized_points": -5.0,
        "unrealized_pnl": -10.0,
        "realized_pnl": -10.0,
        "exit_price": 105.0,
        "close_reason": "STOP_LOSS",
        "point_value": 2.0,
    }


def test_records_closed_winning_trade():
    manager = build_manager()

    result = manager.record(
        position=build_closed_winning_position(),
    )

    assert result["recorded"] is True
    assert result["trade"]["trade_id"]
    assert (
        result["trade"]["position_id"]
        == "position-001"
    )
    assert result["trade"]["symbol"] == "NQ"
    assert result["trade"]["direction"] == "LONG"
    assert result["trade"]["result"] == "WIN"
    assert result["trade"]["realized_pnl"] == 40.0
    assert (
        result["trade"]["close_reason"]
        == "TAKE_PROFIT"
    )


def test_records_closed_losing_trade():
    manager = build_manager()

    result = manager.record(
        position=build_closed_losing_position(),
    )

    assert result["recorded"] is True
    assert result["trade"]["result"] == "LOSS"
    assert result["trade"]["realized_pnl"] == -10.0
    assert (
        result["trade"]["close_reason"]
        == "STOP_LOSS"
    )


def test_records_break_even_trade():
    manager = build_manager()

    position = build_closed_winning_position()
    position["realized_pnl"] = 0.0
    position["exit_price"] = 100.0
    position["close_reason"] = "BREAK_EVEN"

    result = manager.record(
        position=position,
    )

    assert result["trade"]["result"] == "BREAK_EVEN"


def test_rejects_open_position():
    manager = build_manager()

    position = build_closed_winning_position()
    position["status"] = "OPEN"
    position["realized_pnl"] = None

    result = manager.record(
        position=position,
    )

    assert result["recorded"] is False
    assert result["reason"] == "position_not_closed"


def test_rejects_duplicate_position():
    manager = build_manager()

    position = build_closed_winning_position()

    first = manager.record(
        position=position,
    )

    second = manager.record(
        position=position,
    )

    assert first["recorded"] is True
    assert second["recorded"] is False
    assert second["reason"] == "duplicate_position"


def test_returns_complete_history():
    manager = build_manager()

    manager.record(
        position=build_closed_winning_position(),
    )

    manager.record(
        position=build_closed_losing_position(),
    )

    history = manager.get_history()

    assert len(history) == 2
    assert history[0]["position_id"] == "position-001"
    assert history[1]["position_id"] == "position-002"


def test_returns_limited_history():
    manager = build_manager()

    first = build_closed_winning_position()
    second = build_closed_losing_position()
    third = build_closed_winning_position()

    third["position_id"] = "position-003"
    third["order_id"] = "order-003"

    manager.record(
        position=first,
    )

    manager.record(
        position=second,
    )

    manager.record(
        position=third,
    )

    history = manager.get_history(
        limit=2,
    )

    assert len(history) == 2
    assert history[0]["position_id"] == "position-002"
    assert history[1]["position_id"] == "position-003"


def test_calculates_performance_metrics():
    manager = build_manager()

    manager.record(
        position=build_closed_winning_position(),
    )

    manager.record(
        position=build_closed_losing_position(),
    )

    metrics = manager.calculate_metrics()

    assert metrics["total_trades"] == 2
    assert metrics["wins"] == 1
    assert metrics["losses"] == 1
    assert metrics["break_even"] == 0
    assert metrics["win_rate"] == 0.50
    assert metrics["gross_profit"] == 40.0
    assert metrics["gross_loss"] == 10.0
    assert metrics["net_pnl"] == 30.0
    assert metrics["average_win"] == 40.0
    assert metrics["average_loss"] == 10.0
    assert metrics["profit_factor"] == 4.0
    assert metrics["expectancy"] == 15.0


def test_calculates_metrics_with_no_trades():
    manager = build_manager()

    metrics = manager.calculate_metrics()

    assert metrics["total_trades"] == 0
    assert metrics["wins"] == 0
    assert metrics["losses"] == 0
    assert metrics["break_even"] == 0
    assert metrics["win_rate"] == 0.0
    assert metrics["gross_profit"] == 0.0
    assert metrics["gross_loss"] == 0.0
    assert metrics["net_pnl"] == 0.0
    assert metrics["average_win"] == 0.0
    assert metrics["average_loss"] == 0.0
    assert metrics["profit_factor"] == 0.0
    assert metrics["expectancy"] == 0.0


def test_profit_factor_when_there_are_no_losses():
    manager = build_manager()

    manager.record(
        position=build_closed_winning_position(),
    )

    metrics = manager.calculate_metrics()

    assert metrics["profit_factor"] is None


def test_calculates_equity_curve():
    manager = build_manager()

    manager.record(
        position=build_closed_winning_position(),
    )

    manager.record(
        position=build_closed_losing_position(),
    )

    curve = manager.get_equity_curve(
        starting_balance=1000.0,
    )

    assert curve == [
        1000.0,
        1040.0,
        1030.0,
    ]


def test_calculates_maximum_drawdown():
    manager = build_manager()

    first = build_closed_winning_position()

    second = build_closed_losing_position()
    second["realized_pnl"] = -30.0

    third = build_closed_losing_position()
    third["position_id"] = "position-003"
    third["order_id"] = "order-003"
    third["realized_pnl"] = -20.0

    manager.record(
        position=first,
    )

    manager.record(
        position=second,
    )

    manager.record(
        position=third,
    )

    metrics = manager.calculate_metrics(
        starting_balance=1000.0,
    )

    assert metrics["maximum_drawdown"] == 50.0
    assert metrics["ending_balance"] == 990.0


def test_filters_history_by_symbol():
    manager = build_manager()

    nq_position = build_closed_winning_position()

    es_position = build_closed_losing_position()
    es_position["position_id"] = "position-es"
    es_position["order_id"] = "order-es"
    es_position["symbol"] = "ES"

    manager.record(
        position=nq_position,
    )

    manager.record(
        position=es_position,
    )

    history = manager.get_history(
        symbol="NQ",
    )

    assert len(history) == 1
    assert history[0]["symbol"] == "NQ"


def test_rejects_invalid_position_type():
    manager = build_manager()

    with pytest.raises(
        TypeError,
        match="position",
    ):
        manager.record(
            position=object(),
        )


def test_rejects_missing_position_id():
    manager = build_manager()

    position = build_closed_winning_position()
    position["position_id"] = ""

    with pytest.raises(
        ValueError,
        match="position_id",
    ):
        manager.record(
            position=position,
        )


def test_rejects_missing_realized_pnl():
    manager = build_manager()

    position = build_closed_winning_position()
    position["realized_pnl"] = None

    with pytest.raises(
        ValueError,
        match="realized_pnl",
    ):
        manager.record(
            position=position,
        )


def test_rejects_invalid_history_limit():
    manager = build_manager()

    with pytest.raises(
        ValueError,
        match="limit",
    ):
        manager.get_history(
            limit=0,
        )


def test_rejects_invalid_starting_balance():
    manager = build_manager()

    with pytest.raises(
        ValueError,
        match="starting_balance",
    ):
        manager.get_equity_curve(
            starting_balance=0.0,
        )
