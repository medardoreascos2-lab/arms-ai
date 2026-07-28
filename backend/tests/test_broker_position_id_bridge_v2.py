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


def build_signal() -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 23000.0,
        "stop_loss": 22980.0,
        "take_profit": 23040.0,
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


def test_local_position_keeps_broker_position_id():
    lifecycle = build_lifecycle()

    result = lifecycle.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
    )

    assert result["accepted"] is True
    assert result["execution"] is not None
    assert result["position"] is not None

    execution = result["execution"]
    local_position = result["position"]

    assert local_position["position_id"]
    assert local_position["broker_position_id"]
    assert execution["position_id"]

    assert (
        local_position["broker_position_id"]
        == execution["position_id"]
    )

    assert (
        local_position["position_id"]
        != local_position["broker_position_id"]
    )


def test_broker_position_can_be_found_from_local_position():
    lifecycle = build_lifecycle()

    result = lifecycle.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
    )

    local_position = result["position"]

    broker_position = next(
        position
        for position
        in lifecycle
        .broker_connector_v2
        .get_positions()
        if str(
            position["position_id"]
        )
        == str(
            local_position[
                "broker_position_id"
            ]
        )
    )

    assert (
        broker_position["order_id"]
        == local_position["order_id"]
    )

    assert (
        float(
            broker_position["quantity"]
        )
        == float(
            local_position["quantity"]
        )
    )

    assert (
        broker_position["status"]
        == "OPEN"
    )


def test_identity_survives_protection_update():
    lifecycle = build_lifecycle()

    result = lifecycle.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
    )

    position = dict(
        result["position"]
    )

    broker_position_id = (
        position["broker_position_id"]
    )

    position["stop_loss"] = 23000.25

    updated = (
        lifecycle.replace_active_position(
            position=position,
        )
    )

    assert (
        updated["broker_position_id"]
        == broker_position_id
    )

    stored = (
        lifecycle
        .get_active_positions()[0]
    )

    assert (
        stored["broker_position_id"]
        == broker_position_id
    )
