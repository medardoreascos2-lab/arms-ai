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
from backend.execution.portfolio_risk_engine_v2 import (
    PortfolioRiskEngineV2,
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
from backend.execution.exposure_manager_v2 import (
    ExposureManagerV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


def build_risk_manager() -> RiskManagerV2:
    return RiskManagerV2(
        position_sizing_engine=(
            PositionSizingEngineV2()
        ),
        maximum_daily_loss=3000.0,
        maximum_total_drawdown=4500.0,
        maximum_contracts=20,
        maximum_open_positions=5,
    )


def build_exposure_manager() -> ExposureManagerV2:
    return ExposureManagerV2(
        maximum_total_open_risk=500.0,
        maximum_symbol_open_risk=300.0,
        maximum_total_contracts=10,
        maximum_symbol_contracts=6,
    )


def build_portfolio_risk_engine(
) -> PortfolioRiskEngineV2:
    return PortfolioRiskEngineV2(
        maximum_total_open_risk=1000.0,
        maximum_floating_loss=600.0,
        maximum_long_risk=700.0,
        maximum_short_risk=700.0,
        maximum_symbol_risk=500.0,
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
            "account": "PORTFOLIO-RISK-TEST",
            "contracts": contracts,
            "risk_used": risk_amount,
        }


def build_service(
    *,
    portfolio_risk_engine_v2=None,
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
        risk_manager_v2=build_risk_manager(),
        exposure_manager_v2=(
            build_exposure_manager()
        ),
        order_validation_engine_v2=None,
        portfolio_risk_engine_v2=(
            portfolio_risk_engine_v2
        ),
        starting_balance=17000.0,
        execution_risk_gate_v1=(
            ExecutionRiskGateV1(
                validator=FakeApprovedValidator(),
                logger=RiskEventLoggerV1(),
            )
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
        "stop_loss": 90.0,
        "take_profit": 120.0,
        "contracts": 99,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
    }


def build_risk_context() -> dict[str, object]:
    return {
        "account_balance": 17000.0,
        "risk_percent": 0.5,
        "point_value": 2.0,
        "daily_pnl": 0.0,
        "total_drawdown": 0.0,
        "current_price": 100.0,
    }


def test_accepts_none_portfolio_risk_engine():
    service = build_service(
        portfolio_risk_engine_v2=None,
    )

    assert (
        service.portfolio_risk_engine_v2
        is None
    )


def test_accepts_valid_portfolio_risk_engine():
    engine = build_portfolio_risk_engine()

    service = build_service(
        portfolio_risk_engine_v2=engine,
    )

    assert (
        service.portfolio_risk_engine_v2
        is engine
    )


def test_rejects_invalid_portfolio_risk_engine():
    with pytest.raises(
        TypeError,
        match="portfolio_risk_engine_v2",
    ):
        build_service(
            portfolio_risk_engine_v2=object(),
        )


def test_submit_signal_uses_portfolio_risk_engine():
    service = build_service(
        portfolio_risk_engine_v2=(
            build_portfolio_risk_engine()
        ),
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=build_risk_context(),
    )

    assert result["accepted"] is True

    assert (
        result["portfolio_risk_evaluation"][
            "approved"
        ]
        is True
    )

    assert (
        result["portfolio_risk_evaluation"][
            "candidate_contracts"
        ]
        == 4
    )

    assert (
        result["portfolio_risk_evaluation"][
            "candidate_risk"
        ]
        == 80.0
    )


def test_submit_signal_blocks_portfolio_risk():
    engine = PortfolioRiskEngineV2(
        maximum_total_open_risk=50.0,
        maximum_floating_loss=600.0,
        maximum_long_risk=50.0,
        maximum_short_risk=50.0,
        maximum_symbol_risk=50.0,
    )

    service = build_service(
        portfolio_risk_engine_v2=engine,
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=build_risk_context(),
    )

    assert result["accepted"] is False

    assert result["reason"] == (
        "portfolio_risk_blocked"
    )

    assert (
        "maximum_total_open_risk_exceeded"
        in result[
            "portfolio_risk_evaluation"
        ][
            "blocking_reasons"
        ]
    )

    assert result["prepared_order"] is None
    assert result["execution"] is None
    assert result["position"] is None


def test_submit_signal_works_without_portfolio_risk_engine():
    service = build_service(
        portfolio_risk_engine_v2=None,
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=build_risk_context(),
    )

    assert result["accepted"] is True

    assert (
        result["portfolio_risk_evaluation"]
        is None
    )


def test_requires_current_price_when_engine_configured():
    service = build_service(
        portfolio_risk_engine_v2=(
            build_portfolio_risk_engine()
        ),
    )

    risk_context = build_risk_context()
    risk_context.pop(
        "current_price"
    )

    with pytest.raises(
        ValueError,
        match="current_price",
    ):
        service.submit_signal(
            signal=build_signal(),
            order_type="MARKET",
            risk_context=risk_context,
        )
