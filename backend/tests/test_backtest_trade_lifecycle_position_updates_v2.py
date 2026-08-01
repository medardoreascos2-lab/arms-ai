from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)
from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)
from backend.execution.execution_manager_v2 import (
    ExecutionManagerV2,
)
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)
from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


def build_service() -> TradeLifecycleServiceV2:

    return TradeLifecycleServiceV2(
        execution_manager=ExecutionManagerV2(
            execution_mode="PAPER",
            maximum_contracts=20,
        ),
        paper_execution_engine=PaperExecutionEngineV2(
            fill_market_orders_immediately=True,
            slippage_points=0.25,
        ),
        position_manager=PositionManagerV2(
            point_value=2.0,
        ),
        trade_history_manager=TradeHistoryManagerV2(),
        performance_analytics=PerformanceAnalyticsV2(
            risk_free_rate=0.0,
            trading_days_per_year=252,
        ),
        starting_balance=17000.0,
    )


def build_valid_signal() -> dict[str, object]:

    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 20000.0,
        "stop_loss": 19950.0,
        "take_profit": 20100.0,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": (
            "NQ LONG ENTRY 20000.0 "
            "SL 19950.0 TP 20100.0"
        ),
    }


def test_position_can_be_updated_after_submission():

    service = build_service()

    result = service.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
    )

    assert result["accepted"] is True
    assert result["active_position_id"] is not None

    position_id = result["active_position_id"]

    update = service.update_position(
        position_id=position_id,
        current_price=20040.0,
    )

    assert update["updated"] is True
    assert update["position"]["status"] == "OPEN"
    assert update["position"]["current_price"] == 20040.0
    assert update["position"]["unrealized_points"] > 0
    assert update["position"]["unrealized_pnl"] > 0
    assert update["trade_record"] is None


def test_position_closes_at_take_profit_and_records_trade():

    service = build_service()

    submitted = service.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
    )

    assert submitted["accepted"] is True

    position_id = submitted[
        "active_position_id"
    ]

    result = service.update_position(
        position_id=position_id,
        current_price=20100.0,
    )

    assert result["updated"] is True
    assert result["position"]["status"] == "CLOSED"
    assert (
        result["position"]["close_reason"]
        == "TAKE_PROFIT"
    )

    assert result["trade_record"] is not None
    assert result["trade_record"]["recorded"] is True

    trade = result["trade_record"]["trade"]

    assert trade["symbol"] == "NQ"
    assert trade["direction"] == "LONG"
    assert trade["realized_pnl"] > 0

    assert service.get_active_positions() == []

    history = service.get_trade_history()

    assert len(history) == 1
    assert history[0]["symbol"] == "NQ"
    assert history[0]["realized_pnl"] > 0

    metrics = service.get_performance_metrics()

    assert metrics["total_trades"] == 1
    assert metrics["wins"] == 1
    assert metrics["net_pnl"] > 0


def test_position_closes_at_stop_loss_and_records_loss():

    service = build_service()

    submitted = service.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
    )

    assert submitted["accepted"] is True

    position_id = submitted[
        "active_position_id"
    ]

    result = service.update_position(
        position_id=position_id,
        current_price=19950.0,
    )

    assert result["updated"] is True
    assert result["position"]["status"] == "CLOSED"
    assert (
        result["position"]["close_reason"]
        == "STOP_LOSS"
    )

    assert result["trade_record"] is not None
    assert result["trade_record"]["recorded"] is True

    trade = result["trade_record"]["trade"]

    assert trade["symbol"] == "NQ"
    assert trade["direction"] == "LONG"
    assert trade["close_reason"] == "STOP_LOSS"
    assert trade["result"] == "LOSS"
    assert trade["realized_pnl"] < 0

    assert service.get_active_positions() == []

    history = service.get_trade_history()

    assert len(history) == 1
    assert history[0]["result"] == "LOSS"
    assert history[0]["realized_pnl"] < 0

    metrics = service.get_performance_metrics()

    assert metrics["total_trades"] == 1
    assert metrics["wins"] == 0
    assert metrics["losses"] == 1
    assert metrics["net_pnl"] < 0
    assert (
        metrics["ending_balance"]
        < metrics["starting_balance"]
    )
