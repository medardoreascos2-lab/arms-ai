from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)
from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)
from backend.execution.break_even_engine_v2 import (
    BreakEvenEngineV2,
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
from backend.execution.trailing_stop_engine_v2 import (
    TrailingStopEngineV2,
)
from backend.services.live_position_monitor_v2 import (
    LivePositionMonitorV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


def build_signal() -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 120.0,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
    }


def build_lifecycle() -> TradeLifecycleServiceV2:
    return TradeLifecycleServiceV2(
        execution_manager=(
            ExecutionManagerV2(
                execution_mode="PAPER",
                maximum_contracts=20,
            )
        ),
        paper_execution_engine=(
            PaperExecutionEngineV2(
                fill_market_orders_immediately=True,
                slippage_points=0.25,
            )
        ),
        position_manager=(
            PositionManagerV2(
                point_value=2.0,
            )
        ),
        trade_history_manager=(
            TradeHistoryManagerV2()
        ),
        performance_analytics=(
            PerformanceAnalyticsV2(
                risk_free_rate=0.0,
                trading_days_per_year=252,
            )
        ),
        starting_balance=17000.0,
    )


def open_position(
    lifecycle: TradeLifecycleServiceV2,
) -> dict[str, object]:
    result = lifecycle.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
    )

    assert result["accepted"] is True
    assert result["position"] is not None

    return result


def test_break_even_updates_broker_stop():
    lifecycle = build_lifecycle()
    submitted = open_position(
        lifecycle
    )

    position = submitted["position"]
    order_id = str(
        position["order_id"]
    )

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=(
            lifecycle
        ),
        break_even_engine=(
            BreakEvenEngineV2(
                trigger_profit_points=5.0,
                offset_points=0.0,
            )
        ),
        trailing_stop_engine=None,
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=106.0,
    )

    assert result["processed"] is True

    local_position = (
        lifecycle
        .get_active_positions()[0]
    )

    broker_order = next(
        order
        for order
        in lifecycle
        .broker_connector_v2
        .get_orders()
        if str(
            order["order_id"]
        )
        == order_id
    )

    assert (
        local_position["stop_loss"]
        == 100.25
    )

    assert (
        broker_order["stop_loss"]
        == 100.25
    )

    assert (
        broker_order["modified"]
        is True
    )


def test_trailing_stop_updates_broker_stop():
    lifecycle = build_lifecycle()
    submitted = open_position(
        lifecycle
    )

    position = submitted["position"]
    order_id = str(
        position["order_id"]
    )

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=(
            lifecycle
        ),
        break_even_engine=None,
        trailing_stop_engine=(
            TrailingStopEngineV2(
                activation_profit_points=5.0,
                trailing_distance_points=3.0,
            )
        ),
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=110.0,
    )

    assert result["processed"] is True

    local_position = (
        lifecycle
        .get_active_positions()[0]
    )

    broker_order = next(
        order
        for order
        in lifecycle
        .broker_connector_v2
        .get_orders()
        if str(
            order["order_id"]
        )
        == order_id
    )

    assert (
        local_position["stop_loss"]
        == 107.0
    )

    assert (
        broker_order["stop_loss"]
        == 107.0
    )


def test_unchanged_protection_does_not_modify_broker():
    lifecycle = build_lifecycle()
    submitted = open_position(
        lifecycle
    )

    original_position = dict(
        submitted["position"]
    )

    lifecycle.replace_active_position(
        position=original_position,
    )

    broker_order = (
        lifecycle
        .broker_connector_v2
        .get_orders()[0]
    )

    assert (
        broker_order.get(
            "modified",
            False,
        )
        is False
    )


def test_take_profit_change_updates_broker():
    lifecycle = build_lifecycle()
    submitted = open_position(
        lifecycle
    )

    position = dict(
        submitted["position"]
    )

    position[
        "take_profit"
    ] = 125.0

    lifecycle.replace_active_position(
        position=position,
    )

    broker_order = (
        lifecycle
        .broker_connector_v2
        .get_orders()[0]
    )

    assert (
        broker_order["take_profit"]
        == 125.0
    )

    assert (
        lifecycle
        .get_active_positions()[0][
            "take_profit"
        ]
        == 125.0
    )
