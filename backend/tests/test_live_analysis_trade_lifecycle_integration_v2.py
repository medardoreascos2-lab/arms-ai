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
from backend.services.live_analysis_store import (
    LiveAnalysisStore,
)
from backend.services.live_candle_store import (
    LiveCandleStore,
)
from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


def build_lifecycle_service() -> TradeLifecycleServiceV2:
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


def build_live_service(
    *,
    trade_lifecycle_service_v2=None,
) -> LiveMarketAnalysisService:
    return LiveMarketAnalysisService(
        candle_store=LiveCandleStore(),
        analysis_store=LiveAnalysisStore(),
        trade_lifecycle_service_v2=(
            trade_lifecycle_service_v2
        ),
    )


def test_live_service_accepts_none_trade_lifecycle_service():
    service = build_live_service(
        trade_lifecycle_service_v2=None,
    )

    assert (
        service.trade_lifecycle_service_v2
        is None
    )


def test_live_service_accepts_valid_trade_lifecycle_service():
    lifecycle = build_lifecycle_service()

    service = build_live_service(
        trade_lifecycle_service_v2=lifecycle,
    )

    assert (
        service.trade_lifecycle_service_v2
        is lifecycle
    )


def test_live_service_rejects_invalid_trade_lifecycle_service():
    with pytest.raises(
        TypeError,
        match="trade_lifecycle_service_v2",
    ):
        build_live_service(
            trade_lifecycle_service_v2=object(),
        )
