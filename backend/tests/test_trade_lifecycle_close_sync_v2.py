from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)
from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)
from backend.execution.execution_manager_v2 import (
    ExecutionManagerV2,
)
from backend.execution.oco_manager_v2 import (
    OCOManagerV2,
)
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)
from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)
from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)
from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
)
from backend.execution.execution_risk_gate_v1 import (
    ExecutionRiskGateV1,
)
from backend.risk.risk_event_logger_v1 import (
    RiskEventLoggerV1,
)
from backend.execution.protective_order_registry_v2 import (
    ProtectiveOrderRegistryV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


def build_signal(
    *,
    direction: str = "LONG",
) -> dict[str, object]:
    if direction == "LONG":
        stop_loss = 22980.0
        take_profit = 23040.0
    else:
        stop_loss = 23020.0
        take_profit = 22940.0

    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": direction,
        "entry_price": 23000.0,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": f"NQ {direction}",
    }


def build_risk_manager() -> RiskManagerV2:
    return RiskManagerV2(
        position_sizing_engine=PositionSizingEngineV2(),
        maximum_daily_loss=3000.0,
        maximum_total_drawdown=4500.0,
        maximum_contracts=20,
        maximum_open_positions=1,
    )


class FakeApprovedValidator:

    def validate_trade(
        self,
        contracts: int,
        risk_amount: float,
        symbol: str | None = None,
    ):
        return {
            "status": "APPROVED",
            "account": "CLOSE-SYNC-TEST",
            "contracts": contracts,
            "risk_used": risk_amount,
        }


def build_service():
    registry = ProtectiveOrderRegistryV2()
    oco_manager = OCOManagerV2()

    service = TradeLifecycleServiceV2(
        execution_manager=(
            ExecutionManagerV2(
                execution_mode="PAPER",
                maximum_contracts=20,
            )
        ),
        paper_execution_engine=(
            PaperExecutionEngineV2(
                fill_market_orders_immediately=True,
                slippage_points=0.0,
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
        risk_manager_v2=build_risk_manager(),
        starting_balance=17000.0,
        execution_risk_gate_v1=(
            ExecutionRiskGateV1(
                validator=FakeApprovedValidator(),
                logger=RiskEventLoggerV1(),
            )
        ),
        protective_order_registry_v2=registry,
        oco_manager_v2=oco_manager,
    )

    return (
        service,
        registry,
        oco_manager,
    )


def test_take_profit_completes_protection_and_oco():
    (
        service,
        registry,
        oco_manager,
    ) = build_service()

    submitted = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
        },
    )

    position = submitted["position"]

    result = service.update_position(
        position_id=position["position_id"],
        current_price=23040.0,
    )

    protection = registry.get_by_position(
        position_id=position["position_id"],
    )

    group = oco_manager.get_group_by_position(
        position_id=position["position_id"],
    )

    assert (
        result["position"]["close_reason"]
        == "TAKE_PROFIT"
    )

    assert protection is not None
    assert protection["status"] == "COMPLETED"

    assert (
        protection["triggered_order_id"]
        == position["take_profit_order_id"]
    )

    assert (
        protection["take_profit_order_status"]
        == "FILLED"
    )

    assert (
        protection["stop_order_status"]
        == "CANCELLED"
    )

    assert group is not None
    assert group["status"] == "COMPLETED"

    assert (
        group["triggered_order_id"]
        == position["take_profit_order_id"]
    )

    assert (
        group["take_profit_order_status"]
        == "FILLED"
    )

    assert (
        group["stop_order_status"]
        == "CANCELLED"
    )


def test_stop_loss_completes_protection_and_oco():
    (
        service,
        registry,
        oco_manager,
    ) = build_service()

    submitted = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
        },
    )

    position = submitted["position"]

    result = service.update_position(
        position_id=position["position_id"],
        current_price=22980.0,
    )

    protection = registry.get_by_position(
        position_id=position["position_id"],
    )

    group = oco_manager.get_group_by_position(
        position_id=position["position_id"],
    )

    assert (
        result["position"]["close_reason"]
        == "STOP_LOSS"
    )

    assert protection is not None
    assert protection["status"] == "COMPLETED"

    assert (
        protection["triggered_order_id"]
        == position["stop_order_id"]
    )

    assert (
        protection["stop_order_status"]
        == "FILLED"
    )

    assert (
        protection["take_profit_order_status"]
        == "CANCELLED"
    )

    assert group is not None
    assert group["status"] == "COMPLETED"

    assert (
        group["triggered_order_id"]
        == position["stop_order_id"]
    )

    assert (
        group["stop_order_status"]
        == "FILLED"
    )

    assert (
        group["take_profit_order_status"]
        == "CANCELLED"
    )


def test_manual_close_cancels_protection_and_oco():
    (
        service,
        registry,
        oco_manager,
    ) = build_service()

    submitted = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
        },
    )

    position = dict(
        submitted["position"]
    )

    position.update(
        {
            "status": "CLOSED",
            "close_reason": "MANUAL",
            "exit_price": 23010.0,
        }
    )

    sync_result = (
        service
        ._sync_protection_and_oco_after_close(
            position=position,
        )
    )

    protection = registry.get_by_position(
        position_id=position["position_id"],
    )

    group = oco_manager.get_group_by_position(
        position_id=position["position_id"],
    )

    assert sync_result["synchronized"] is True
    assert sync_result["status"] == "CANCELLED"

    assert protection is not None
    assert protection["status"] == "CANCELLED"

    assert (
        protection["stop_order_status"]
        == "CANCELLED"
    )

    assert (
        protection["take_profit_order_status"]
        == "CANCELLED"
    )

    assert group is not None
    assert group["status"] == "CANCELLED"

    assert (
        group["stop_order_status"]
        == "CANCELLED"
    )

    assert (
        group["take_profit_order_status"]
        == "CANCELLED"
    )


def test_close_sync_is_idempotent():
    (
        service,
        registry,
        oco_manager,
    ) = build_service()

    submitted = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
        },
    )

    position = dict(
        submitted["position"]
    )

    position.update(
        {
            "status": "CLOSED",
            "close_reason": "TAKE_PROFIT",
            "exit_price": 23040.0,
        }
    )

    first = (
        service
        ._sync_protection_and_oco_after_close(
            position=position,
        )
    )

    second = (
        service
        ._sync_protection_and_oco_after_close(
            position=position,
        )
    )

    protection = registry.get_by_position(
        position_id=position["position_id"],
    )

    group = oco_manager.get_group_by_position(
        position_id=position["position_id"],
    )

    assert first["synchronized"] is True
    assert second["synchronized"] is True

    assert protection is not None
    assert protection["status"] == "COMPLETED"

    assert group is not None
    assert group["status"] == "COMPLETED"

    assert (
        second["oco"]["idempotent"]
        is True
    )

    registry_snapshot = registry.snapshot()
    oco_snapshot = oco_manager.snapshot()

    assert (
        registry_snapshot[
            "total_protections"
        ]
        == 1
    )

    assert (
        registry_snapshot[
            "completed_protections"
        ]
        == 1
    )

    assert oco_snapshot["total_groups"] == 1
    assert oco_snapshot["completed_groups"] == 1


def test_close_sync_skips_missing_group_ids():
    (
        service,
        registry,
        oco_manager,
    ) = build_service()

    result = (
        service
        ._sync_protection_and_oco_after_close(
            position={
                "position_id": "legacy-position",
                "status": "CLOSED",
                "close_reason": "MANUAL",
            },
        )
    )

    assert result["synchronized"] is False

    assert (
        result["status"]
        == "MISSING_GROUP_IDS"
    )

    assert (
        registry.snapshot()[
            "total_protections"
        ]
        == 0
    )

    assert (
        oco_manager.snapshot()[
            "total_groups"
        ]
        == 0
    )
