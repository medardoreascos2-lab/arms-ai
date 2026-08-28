from backend.risk.risk_event_logger_v1 import (
    RiskEventLoggerV1,
)
from backend.execution.execution_risk_gate_v1 import (
    ExecutionRiskGateV1,
)
from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
)
from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)
import pytest

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


def build_risk_context() -> dict[str, object]:
    return {
        "account_balance": 17000.0,
        "risk_percent": 0.5,
        "point_value": 2.0,
        "daily_pnl": 0.0,
        "total_drawdown": 0.0,
    }


def build_service(
    *,
    registry=None,
) -> TradeLifecycleServiceV2:
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
        execution_risk_gate_v1=ExecutionRiskGateV1(
            validator=FakeApprovedValidator(),
            logger=RiskEventLoggerV1(),
        ),
        protective_order_registry_v2=registry,
    )


def test_creates_default_registry():
    service = build_service()

    assert isinstance(
        service.protective_order_registry_v2,
        ProtectiveOrderRegistryV2,
    )


def test_uses_injected_registry():
    registry = ProtectiveOrderRegistryV2()

    service = build_service(
        registry=registry,
    )

    assert (
        service.protective_order_registry_v2
        is registry
    )


def test_rejects_invalid_registry():
    with pytest.raises(
        TypeError,
        match="protective_order_registry_v2",
    ):
        build_service(
            registry=object(),
        )


@pytest.mark.parametrize(
    "direction",
    [
        "LONG",
        "SHORT",
    ],
)
def test_open_position_creates_protection(
    direction,
):
    registry = ProtectiveOrderRegistryV2()

    service = build_service(
        registry=registry,
    )

    result = service.submit_signal(
        signal=build_signal(
            direction=direction,
        ),
        order_type="MARKET",
        risk_context=build_risk_context(),
    )

    assert result["accepted"] is True
    assert result["position"] is not None

    position = result["position"]

    protection = registry.get_by_position(
        position_id=position["position_id"],
        active_only=True,
    )

    assert protection is not None

    assert (
        protection["position_id"]
        == position["position_id"]
    )

    assert (
        protection["broker_position_id"]
        == position["broker_position_id"]
    )

    assert (
        protection["symbol"]
        == position["symbol"]
    )

    assert (
        protection["direction"]
        == direction
    )

    assert (
        protection["quantity"]
        == float(
            position["quantity"]
        )
    )

    assert (
        protection["entry_price"]
        == float(
            position["entry_price"]
        )
    )

    assert (
        protection["stop_price"]
        == float(
            position["stop_loss"]
        )
    )

    assert (
        protection["take_profit_price"]
        == float(
            position["take_profit"]
        )
    )

    assert (
        position["protection_group_id"]
        == protection[
            "protection_group_id"
        ]
    )

    assert (
        position["stop_order_id"]
        == protection["stop_order_id"]
    )

    assert (
        position["take_profit_order_id"]
        == protection[
            "take_profit_order_id"
        ]
    )


def test_active_position_keeps_protection_ids():
    service = build_service()

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=build_risk_context(),
    )

    stored_position = (
        service.get_active_positions()[0]
    )

    assert (
        stored_position[
            "protection_group_id"
        ]
        == result["position"][
            "protection_group_id"
        ]
    )

    assert stored_position["stop_order_id"]

    assert (
        stored_position[
            "take_profit_order_id"
        ]
    )


def test_registry_snapshot_reports_active_protection():
    service = build_service()

    service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=build_risk_context(),
    )

    snapshot = (
        service
        .protective_order_registry_v2
        .snapshot()
    )

    assert snapshot["total_protections"] == 1
    assert snapshot["active_protections"] == 1
    assert snapshot["completed_protections"] == 0
    assert snapshot["cancelled_protections"] == 0

class FakeApprovedValidator:
    def validate_trade(
        self,
        contracts: int,
        risk_amount: float,
        symbol: str | None = None,
    ):
        return {
            "status": "APPROVED",
            "account": "TEST",
            "contracts": contracts,
            "risk_used": risk_amount,
        }
