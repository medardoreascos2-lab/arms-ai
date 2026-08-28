from backend.risk.risk_event_logger_v1 import (
    RiskEventLoggerV1,
)
from backend.execution.execution_risk_gate_v1 import (
    ExecutionRiskGateV1,
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
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


def build_service() -> TradeLifecycleServiceV2:
    return TradeLifecycleServiceV2(
        execution_manager=ExecutionManagerV2(
            execution_mode="PAPER",
            maximum_contracts=20,
        ),
        paper_execution_engine=(
            PaperExecutionEngineV2(
                fill_market_orders_immediately=True,
                slippage_points=0.0,
            )
        ),
        position_manager=PositionManagerV2(
            point_value=2.0,
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
        execution_risk_gate_v1=ExecutionRiskGateV1(
            validator=FakeApprovedValidator(),
            logger=RiskEventLoggerV1(),
        ),
    )


def build_position() -> dict[str, object]:
    return {
        "opened": True,
        "position_id": "position-recovery-001",
        "broker_position_id": (
            "broker-position-001"
        ),
        "order_id": "order-001",
        "symbol": "nq",
        "direction": "long",
        "quantity": 2,
        "entry_price": 23000.0,
        "current_price": 23010.0,
        "stop_loss": 22980.0,
        "take_profit": 23040.0,
        "point_value": 2.0,
        "unrealized_points": 10.0,
        "unrealized_pnl": 40.0,
        "realized_pnl": 0.0,
        "status": "open",
        "exit_price": None,
        "close_reason": None,
        "execution_mode": "PAPER",
        "protection_group_id": (
            "protection-001"
        ),
        "oco_group_id": "oco-001",
        "stop_order_id": "stop-001",
        "take_profit_order_id": "tp-001",
    }


def test_restores_active_position() -> None:
    service = build_service()
    position = build_position()

    restored = service.restore_active_position(
        position=position,
    )

    assert restored["position_id"] == (
        "position-recovery-001"
    )
    assert restored["symbol"] == "NQ"
    assert restored["direction"] == "LONG"
    assert restored["status"] == "OPEN"
    assert restored["quantity"] == 2.0

    active_positions = (
        service.get_active_positions()
    )

    assert len(active_positions) == 1
    assert active_positions[0] == restored


def test_restore_is_idempotent() -> None:
    service = build_service()
    position = build_position()

    first = service.restore_active_position(
        position=position,
    )

    second = service.restore_active_position(
        position=dict(first),
    )

    assert first == second

    assert len(
        service.get_active_positions()
    ) == 1


def test_rejects_conflicting_position_id() -> None:
    service = build_service()
    position = build_position()

    service.restore_active_position(
        position=position,
    )

    conflicting = dict(position)
    conflicting["quantity"] = 3

    with pytest.raises(
        ValueError,
        match="mismo position_id",
    ):
        service.restore_active_position(
            position=conflicting,
        )


def test_rejects_closed_position() -> None:
    service = build_service()
    position = build_position()
    position["status"] = "CLOSED"

    with pytest.raises(
        ValueError,
        match="status OPEN",
    ):
        service.restore_active_position(
            position=position,
        )


def test_rejects_missing_position_id() -> None:
    service = build_service()
    position = build_position()
    position.pop("position_id")

    with pytest.raises(
        ValueError,
        match="position_id",
    ):
        service.restore_active_position(
            position=position,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "symbol",
            "",
            "symbol",
        ),
        (
            "direction",
            "SIDEWAYS",
            "direction",
        ),
        (
            "quantity",
            0,
            "quantity",
        ),
    ],
)
def test_rejects_invalid_required_fields(
    field: str,
    value: object,
    message: str,
) -> None:
    service = build_service()
    position = build_position()
    position[field] = value

    with pytest.raises(
        ValueError,
        match=message,
    ):
        service.restore_active_position(
            position=position,
        )


def test_returns_defensive_copies() -> None:
    service = build_service()
    position = build_position()

    restored = service.restore_active_position(
        position=position,
    )

    restored["symbol"] = "ES"

    active = service.get_active_positions()

    assert active[0]["symbol"] == "NQ"

    active[0]["symbol"] = "CL"

    assert (
        service.get_active_positions()[0][
            "symbol"
        ]
        == "NQ"
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
            "account": "TEST",
            "contracts": contracts,
            "risk_used": risk_amount,
        }
