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
from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
)
from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)
from backend.services.live_position_monitor_v2 import (
    LivePositionMonitorV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
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
        risk_manager_v2=build_risk_manager(),
        starting_balance=17000.0,
        execution_risk_gate_v1=ExecutionRiskGateV1(
            validator=FakeApprovedValidator(),
            logger=RiskEventLoggerV1(),
        ),
    )


def build_monitor() -> LivePositionMonitorV2:
    return LivePositionMonitorV2(
        trade_lifecycle_service=(
            build_lifecycle()
        )
    )


def build_long_signal() -> dict[str, object]:
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
        "summary": (
            "NQ LONG ENTRY 100.0 "
            "SL 95.0 TP 110.0"
        ),
    }


def build_short_signal() -> dict[str, object]:
    signal = build_long_signal()

    signal.update(
        {
            "direction": "SHORT",
            "entry_price": 100.0,
            "stop_loss": 105.0,
            "take_profit": 90.0,
        }
    )

    return signal


def open_position(
    monitor: LivePositionMonitorV2,
    *,
    signal: dict[str, object],
) -> dict[str, object]:
    return (
        monitor.trade_lifecycle_service.submit_signal(
            signal=signal,
            order_type="MARKET",
            risk_context=build_risk_context(),
        )
    )


def test_processes_price_without_active_position():
    monitor = build_monitor()

    result = monitor.process_price(
        symbol="NQ",
        current_price=105.0,
    )

    assert result["processed"] is True
    assert result["symbol"] == "NQ"
    assert result["current_price"] == 105.0
    assert result["matched_positions"] == 0
    assert result["updated_positions"] == []
    assert result["closed_positions"] == 0


def test_updates_matching_open_position():
    monitor = build_monitor()

    opened = open_position(
        monitor,
        signal=build_long_signal(),
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=105.25,
    )

    assert result["matched_positions"] == 1
    assert len(
        result["updated_positions"]
    ) == 1

    updated = result[
        "updated_positions"
    ][0]

    assert (
        updated["position"][
            "position_id"
        ]
        == opened["active_position_id"]
    )

    assert (
        updated["position"][
            "status"
        ]
        == "OPEN"
    )

    assert (
        updated["position"][
            "current_price"
        ]
        == 105.25
    )

    assert (
        updated["position"][
            "unrealized_pnl"
        ]
        == 20.0
    )


def test_ignores_position_from_other_symbol():
    monitor = build_monitor()

    open_position(
        monitor,
        signal=build_long_signal(),
    )

    result = monitor.process_price(
        symbol="ES",
        current_price=105.0,
    )

    assert result["matched_positions"] == 0
    assert result["updated_positions"] == []

    active = (
        monitor.trade_lifecycle_service
        .get_active_positions()
    )

    assert len(active) == 1
    assert active[0]["symbol"] == "NQ"


def test_closes_long_position_at_take_profit():
    monitor = build_monitor()

    open_position(
        monitor,
        signal=build_long_signal(),
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=110.0,
    )

    assert result["matched_positions"] == 1
    assert result["closed_positions"] == 1

    updated = result[
        "updated_positions"
    ][0]

    assert (
        updated["position"][
            "status"
        ]
        == "CLOSED"
    )

    assert (
        updated["position"][
            "close_reason"
        ]
        == "TAKE_PROFIT"
    )

    assert (
        updated["trade_record"][
            "recorded"
        ]
        is True
    )


def test_closes_long_position_at_stop_loss():
    monitor = build_monitor()

    open_position(
        monitor,
        signal=build_long_signal(),
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=95.0,
    )

    assert result["closed_positions"] == 1

    updated = result[
        "updated_positions"
    ][0]

    assert (
        updated["position"][
            "close_reason"
        ]
        == "STOP_LOSS"
    )

    assert (
        updated["position"][
            "realized_pnl"
        ]
        < 0
    )


def test_closes_short_position_at_take_profit():
    monitor = build_monitor()

    open_position(
        monitor,
        signal=build_short_signal(),
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=90.0,
    )

    assert result["closed_positions"] == 1

    updated = result[
        "updated_positions"
    ][0]

    assert (
        updated["position"][
            "direction"
        ]
        == "SHORT"
    )

    assert (
        updated["position"][
            "close_reason"
        ]
        == "TAKE_PROFIT"
    )

    assert (
        updated["position"][
            "realized_pnl"
        ]
        > 0
    )


def test_returns_performance_after_close():
    monitor = build_monitor()

    open_position(
        monitor,
        signal=build_long_signal(),
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=110.0,
    )

    metrics = result[
        "performance_metrics"
    ]

    assert metrics is not None
    assert metrics["total_trades"] == 1
    assert metrics["wins"] == 1
    assert metrics["net_pnl"] > 0


def test_removes_closed_position():
    monitor = build_monitor()

    open_position(
        monitor,
        signal=build_long_signal(),
    )

    monitor.process_price(
        symbol="NQ",
        current_price=110.0,
    )

    active = (
        monitor.trade_lifecycle_service
        .get_active_positions()
    )

    assert active == []


def test_normalizes_symbol():
    monitor = build_monitor()

    open_position(
        monitor,
        signal=build_long_signal(),
    )

    result = monitor.process_price(
        symbol=" nq ",
        current_price=105.0,
    )

    assert result["symbol"] == "NQ"
    assert result["matched_positions"] == 1


def test_rejects_empty_symbol():
    monitor = build_monitor()

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        monitor.process_price(
            symbol="",
            current_price=105.0,
        )


def test_rejects_invalid_current_price():
    monitor = build_monitor()

    with pytest.raises(
        ValueError,
        match="current_price",
    ):
        monitor.process_price(
            symbol="NQ",
            current_price=0.0,
        )


def test_rejects_invalid_lifecycle_service():
    with pytest.raises(
        TypeError,
        match="trade_lifecycle_service",
    ):
        LivePositionMonitorV2(
            trade_lifecycle_service=object(),
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
