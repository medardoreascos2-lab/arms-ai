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
from backend.execution.partial_take_profit_engine_v2 import (
    PartialTakeProfitEngineV2,
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
from backend.execution.realized_pnl_engine_v2 import (
    RealizedPnLEngineV2,
)
from backend.portfolio.portfolio_manager_v2 import (
    PortfolioManagerV2,
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
        "contracts": 4,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
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
            "account": "LIVE-PARTIAL-CLOSE-TEST",
            "contracts": contracts,
            "risk_used": risk_amount,
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
        portfolio_manager_v2=(
            PortfolioManagerV2(
                starting_balance=17000.0,
            )
        ),
    )


def test_partial_take_profit_syncs_broker_and_portfolio():
    lifecycle = build_lifecycle()

    submitted = lifecycle.submit_signal(
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

    local_position = submitted["position"]

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=(
            lifecycle
        ),
        partial_take_profit_engine=(
            PartialTakeProfitEngineV2(
                trigger_profit_points=10.0,
                close_fraction=0.50,
            )
        ),
        realized_pnl_engine=(
            RealizedPnLEngineV2(
                point_value=2.0,
            )
        ),
        break_even_engine=None,
        trailing_stop_engine=None,
        portfolio_manager_v2=(
            lifecycle.portfolio_manager_v2
        ),
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=110.0,
    )

    assert result["processed"] is True

    stored_local = (
        lifecycle
        .get_active_positions()[0]
    )

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

    portfolio_position = (
        lifecycle
        .portfolio_manager_v2
        .get_open_positions()[0]
    )

    assert stored_local["quantity"] == 2.0
    assert broker_position["quantity"] == 2.0
    assert portfolio_position["quantity"] == 2.0

    assert stored_local["partial_taken"] is True
    assert (
        stored_local[
            "partial_closed_quantity"
        ]
        == 2.0
    )

    partial_fills = [
        fill
        for fill
        in lifecycle
        .broker_connector_v2
        .get_fills()
        if fill.get(
            "fill_type"
        )
        == "PARTIAL_CLOSE"
    ]

    assert len(partial_fills) == 1
    assert (
        partial_fills[0]["quantity"]
        == 2.0
    )


def test_partial_close_is_not_sent_twice():
    lifecycle = build_lifecycle()

    lifecycle.submit_signal(
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

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=(
            lifecycle
        ),
        partial_take_profit_engine=(
            PartialTakeProfitEngineV2(
                trigger_profit_points=10.0,
                close_fraction=0.50,
            )
        ),
        realized_pnl_engine=(
            RealizedPnLEngineV2(
                point_value=2.0,
            )
        ),
        break_even_engine=None,
        trailing_stop_engine=None,
    )

    monitor.process_price(
        symbol="NQ",
        current_price=110.0,
    )

    monitor.process_price(
        symbol="NQ",
        current_price=112.0,
    )

    partial_fills = [
        fill
        for fill
        in lifecycle
        .broker_connector_v2
        .get_fills()
        if fill.get(
            "fill_type"
        )
        == "PARTIAL_CLOSE"
    ]

    assert len(partial_fills) == 1
