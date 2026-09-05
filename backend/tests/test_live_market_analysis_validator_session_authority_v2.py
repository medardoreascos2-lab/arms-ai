from __future__ import annotations

import ast
from pathlib import Path


LIVE = Path(
    "backend/services/live_market_analysis_service.py"
)


def _validator_session_allowed_expression() -> ast.expr:
    tree = ast.parse(
        LIVE.read_text(
            encoding="utf-8",
        )
    )

    matches: list[ast.expr] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "validate"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "trade_validator_v2"
        ):
            continue

        for keyword in node.keywords:
            if keyword.arg == "session_allowed":
                matches.append(keyword.value)

    assert len(matches) == 1

    return matches[0]


def test_trade_validator_session_allowed_is_not_static_true():
    value = _validator_session_allowed_expression()

    assert not (
        isinstance(value, ast.Constant)
        and value.value is True
    ), (
        "TradeValidatorV2 still receives "
        "session_allowed=True instead of "
        "canonical market-hours authority."
    )


def test_trade_validator_session_allowed_uses_market_hours_authority():
    value = _validator_session_allowed_expression()

    rendered = ast.unparse(value)

    assert (
        "market_is_open" in rendered
        or "market_hours" in rendered
    ), (
        "TradeValidatorV2 session_allowed must derive "
        "from canonical MarketHoursServiceV2 authority. "
        f"Current expression: {rendered}"
    )


def test_runtime_open_market_reaches_validator_as_session_allowed_true():
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.execution.trade_validator_v2 import (
        TradeValidatorV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )
    from backend.models.candle import Candle
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

    chicago = ZoneInfo(
        "America/Chicago"
    )

    store = LiveCandleStore()

    base = datetime(
        2026,
        8,
        18,
        10,
        0,
        tzinfo=chicago,
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

    market_hours = MarketHoursServiceV2(
        calendar_resolver=(
            lambda symbol, timestamp: True
        ),
    )

    service = LiveMarketAnalysisService(
        candle_store=store,
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
        market_hours_service_v2=market_hours,
    )

    # Isolate this test from wall-clock freshness.
    service._calculate_signal_age_seconds = (
        lambda *_args, **_kwargs: 0
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    validation = result[
        "trade_validation_v2"
    ]

    assert (
        validation["inputs"][
            "session_allowed"
        ]
        is True
    )

    assert (
        "session_not_allowed"
        not in validation[
            "blocking_reasons"
        ]
    )


def test_runtime_closed_market_reaches_validator_as_session_allowed_false():
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.execution.trade_validator_v2 import (
        TradeValidatorV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )
    from backend.models.candle import Candle
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

    chicago = ZoneInfo(
        "America/Chicago"
    )

    store = LiveCandleStore()

    base = datetime(
        2026,
        8,
        18,
        10,
        0,
        tzinfo=chicago,
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

    market_hours = MarketHoursServiceV2(
        calendar_resolver=(
            lambda symbol, timestamp: False
        ),
    )

    service = LiveMarketAnalysisService(
        candle_store=store,
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
        market_hours_service_v2=market_hours,
    )

    # Isolate this test from wall-clock freshness.
    service._calculate_signal_age_seconds = (
        lambda *_args, **_kwargs: 0
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    validation = result[
        "trade_validation_v2"
    ]

    assert (
        validation["inputs"][
            "session_allowed"
        ]
        is False
    )

    assert (
        "session_not_allowed"
        in validation[
            "blocking_reasons"
        ]
    )

    assert (
        validation["approved"]
        is False
    )

    assert (
        validation["decision"]
        == "BLOCK"
    )
