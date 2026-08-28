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
from backend.execution.order_validation_engine_v2 import (
    OrderValidationEngineV2,
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


def build_order_validator(
) -> OrderValidationEngineV2:
    return OrderValidationEngineV2(
        minimum_reward_risk_ratio=2.0,
        minimum_stop_points=2.0,
        maximum_stop_points=50.0,
        allowed_symbols={
            "NQ",
            "MNQ",
            "ES",
            "MES",
        },
    )


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
    order_validation_engine_v2=None,
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
        order_validation_engine_v2=(
            order_validation_engine_v2
        ),
        risk_manager_v2=build_risk_manager(),
        starting_balance=17000.0,
        execution_risk_gate_v1=ExecutionRiskGateV1(
            validator=FakeApprovedValidator(),
            logger=RiskEventLoggerV1(),
        ),
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
        "take_profit": 110.0,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
    }


def test_accepts_none_order_validation_engine():
    service = build_service(
        order_validation_engine_v2=None,
    )

    assert (
        service.order_validation_engine_v2
        is None
    )


def test_accepts_valid_order_validation_engine():
    validator = build_order_validator()

    service = build_service(
        order_validation_engine_v2=validator,
    )

    assert (
        service.order_validation_engine_v2
        is validator
    )


def test_rejects_invalid_order_validation_engine():
    with pytest.raises(
        TypeError,
        match="order_validation_engine_v2",
    ):
        build_service(
            order_validation_engine_v2=object(),
        )


def test_submit_signal_uses_order_validation():
    service = build_service(
        order_validation_engine_v2=(
            build_order_validator()
        ),
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=build_risk_context(),
        order_context={
            "market_is_open": True,
        },
    )

    assert result["accepted"] is True

    assert (
        result["order_validation"][
            "approved"
        ]
        is True
    )

    assert (
        result["order_validation"][
            "decision"
        ]
        == "ALLOW_ORDER"
    )

    assert (
        result["execution"]["status"]
        == "FILLED"
    )

    assert (
        result["position"]["status"]
        == "OPEN"
    )


def test_submit_signal_blocks_closed_market():
    service = build_service(
        order_validation_engine_v2=(
            build_order_validator()
        ),
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=build_risk_context(),
        order_context={
            "market_is_open": False,
        },
    )

    assert result["accepted"] is False
    assert result["reason"] == (
        "order_validation_blocked"
    )

    assert (
        "market_closed"
        in result["order_validation"][
            "blocking_reasons"
        ]
    )

    assert result["execution"] is None
    assert result["position"] is None
    assert result["active_position_id"] is None


def test_submit_signal_blocks_disallowed_symbol():
    service = build_service(
        order_validation_engine_v2=(
            build_order_validator()
        ),
    )

    signal = build_signal()
    signal["symbol"] = "CL"

    result = service.submit_signal(
        signal=signal,
        order_type="MARKET",
        risk_context=build_risk_context(),
        order_context={
            "market_is_open": True,
        },
    )

    assert result["accepted"] is False

    assert (
        "symbol_not_allowed"
        in result["order_validation"][
            "blocking_reasons"
        ]
    )

    assert result["execution"] is None


def test_submit_signal_blocks_invalid_reward_risk():
    service = build_service(
        order_validation_engine_v2=(
            build_order_validator()
        ),
    )

    signal = build_signal()
    signal["take_profit"] = 107.0

    result = service.submit_signal(
        signal=signal,
        order_type="MARKET",
        risk_context=build_risk_context(),
        order_context={
            "market_is_open": True,
        },
    )

    assert result["accepted"] is False

    assert (
        result["order_validation"][
            "reward_risk_ratio"
        ]
        == 1.4
    )

    assert (
        "reward_risk_below_minimum"
        in result["order_validation"][
            "blocking_reasons"
        ]
    )


def test_requires_order_context_when_validator_configured():
    service = build_service(
        order_validation_engine_v2=(
            build_order_validator()
        ),
    )

    with pytest.raises(
        ValueError,
        match="order_context",
    ):
        service.submit_signal(
            signal=build_signal(),
            order_type="MARKET",
        risk_context=build_risk_context(),
        )


def test_rejects_invalid_order_context_type():
    service = build_service(
        order_validation_engine_v2=(
            build_order_validator()
        ),
    )

    with pytest.raises(
        ValueError,
        match="order_context",
    ):
        service.submit_signal(
            signal=build_signal(),
            order_type="MARKET",
        risk_context=build_risk_context(),
            order_context=object(),
        )


def test_submit_signal_works_without_validator():
    service = build_service(
        order_validation_engine_v2=None,
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=build_risk_context(),
    )

    assert result["accepted"] is True
    assert result["order_validation"] is None


def test_validator_receives_open_symbols():
    service = build_service(
        order_validation_engine_v2=(
            build_order_validator()
        ),
    )

    first_result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=build_risk_context(),
        order_context={
            "market_is_open": True,
        },
    )

    assert first_result["accepted"] is True

    second_result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=build_risk_context(),
        order_context={
            "market_is_open": True,
        },
    )

    assert second_result["accepted"] is False
    assert (
        second_result["reason"]
        == "position_already_open"
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
