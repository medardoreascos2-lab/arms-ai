from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend.execution.execution_decision_engine_v2 import (
    ExecutionDecisionEngineV2,
)
from backend.intelligence.confluence_engine_v2 import (
    ConfluenceEngineV2,
)
from backend.intelligence.probability_engine_v2 import (
    ProbabilityEngineV2,
)
from backend.execution.trade_planner_v2 import (
    TradePlannerV2,
)
from backend.execution.trade_validator_v2 import (
    TradeValidatorV2,
)
from backend.signals.signal_generator_v2 import (
    SignalGeneratorV2,
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
from backend.services.market_hours_service_v2 import (
    MarketHoursServiceV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)
from backend.account.account_state_manager_v2 import (
    AccountStateManagerV2,
)
from backend.portfolio.portfolio_manager_v2 import (
    PortfolioManagerV2,
)


CHICAGO = ZoneInfo("America/Chicago")


class RecordingTradeLifecycleServiceV2(
    TradeLifecycleServiceV2
):
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

        account_state_manager_v2 = (
            AccountStateManagerV2(
                starting_balance=17000.0,
                maximum_daily_loss=3000.0,
                maximum_total_drawdown=4500.0,
            )
        )

        self.portfolio_manager_v2 = (
            PortfolioManagerV2(
                starting_balance=17000.0,
                account_state_manager_v2=(
                    account_state_manager_v2
                ),
            )
        )

    def submit_signal(
        self,
        *,
        signal: dict[str, object],
        order_type: str,
        risk_context: dict[str, object],
        order_context: dict[str, object],
    ) -> dict[str, object]:
        self.calls.append(
            {
                "signal": signal,
                "order_type": order_type,
                "risk_context": risk_context,
                "order_context": order_context,
            }
        )

        return {
            "prepared_order": {
                "status": "TEST",
            },
        }


def _build_store() -> LiveCandleStore:
    from backend.models.candle import Candle

    store = LiveCandleStore()

    base = datetime(
        2026,
        8,
        18,
        10,
        0,
        tzinfo=CHICAGO,
    )

    for index in range(60):
        store.add(
            Candle(
                symbol="NQ",
                timeframe="5m",
                timestamp=(
                    base
                    + timedelta(
                        minutes=index * 5
                    )
                ),
                open=20000.0 + index,
                high=20001.0 + index,
                low=19999.0 + index,
                close=20000.5 + index,
                volume=1000.0,
            )
        )

    return store


def _always_open_calendar(
    symbol: str,
    timestamp: datetime,
) -> bool | None:
    return True


def _always_closed_calendar(
    symbol: str,
    timestamp: datetime,
) -> bool | None:
    return False


def _build_service(
    *,
    lifecycle: RecordingTradeLifecycleServiceV2,
    market_hours_service_v2: MarketHoursServiceV2 | None,
) -> LiveMarketAnalysisService:
    return LiveMarketAnalysisService(
        candle_store=_build_store(),
        analysis_store=LiveAnalysisStore(),
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
            )
        ),
        trade_planner_v2=(
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        ),
        trade_validator_v2=(
            TradeValidatorV2(
                minimum_reward_risk_ratio=2.0,
                minimum_stop_points=2.0,
                maximum_stop_points=50.0,
                maximum_spread_points=1.0,
                minimum_atr_points=3.0,
                maximum_signal_age_seconds=30,
            )
        ),
        signal_generator_v2=(
            SignalGeneratorV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
                allowed_grades={
                    "A+",
                    "A",
                },
            )
        ),
        trade_lifecycle_service_v2=lifecycle,
        market_hours_service_v2=(
            market_hours_service_v2
        ),
    )

def _run(
    service: LiveMarketAnalysisService,
) -> dict[str, object]:
    return service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )


def test_live_wiring_fails_closed_without_market_hours_service():
    lifecycle = RecordingTradeLifecycleServiceV2()

    service = _build_service(
        lifecycle=lifecycle,
        market_hours_service_v2=None,
    )

    _run(service)

    assert lifecycle.calls, (
        "Expected analysis to reach trade lifecycle."
    )

    assert (
        lifecycle.calls[-1]["order_context"][
            "market_is_open"
        ]
        is False
    )


def test_live_wiring_passes_open_market_to_lifecycle():
    lifecycle = RecordingTradeLifecycleServiceV2()

    market_hours = MarketHoursServiceV2(
        calendar_resolver=_always_open_calendar,
    )

    service = _build_service(
        lifecycle=lifecycle,
        market_hours_service_v2=market_hours,
    )

    _run(service)

    assert lifecycle.calls, (
        "Expected analysis to reach trade lifecycle."
    )

    assert (
        lifecycle.calls[-1]["order_context"][
            "market_is_open"
        ]
        is True
    )


def test_live_wiring_passes_closed_market_to_lifecycle():
    lifecycle = RecordingTradeLifecycleServiceV2()

    market_hours = MarketHoursServiceV2(
        calendar_resolver=_always_closed_calendar,
    )

    service = _build_service(
        lifecycle=lifecycle,
        market_hours_service_v2=market_hours,
    )

    _run(service)

    assert lifecycle.calls, (
        "Expected analysis to reach trade lifecycle."
    )

    assert (
        lifecycle.calls[-1]["order_context"][
            "market_is_open"
        ]
        is False
    )


def test_live_wiring_rejects_invalid_market_hours_service():
    with pytest.raises(
        TypeError,
        match="market_hours_service_v2",
    ):
        LiveMarketAnalysisService(
            candle_store=LiveCandleStore(),
            analysis_store=LiveAnalysisStore(),
            market_hours_service_v2=object(),
        )
