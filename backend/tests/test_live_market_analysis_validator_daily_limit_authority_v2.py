from __future__ import annotations

import ast
from pathlib import Path
from backend.execution.signal_execution_manager import SignalExecutionManager


class AlwaysAcceptExecutionManager(
    SignalExecutionManager
):
    def evaluate(
        self,
        signal,
    ):
        return {
            **signal,
            "accepted": True,
            "status": "ACCEPTED",
        }


LIVE_PATH = Path(
    "backend/services/live_market_analysis_service.py"
)


def _tree() -> ast.Module:
    return ast.parse(
        LIVE_PATH.read_text(
            encoding="utf-8",
        )
    )


def _keyword_values(
    *,
    function_name: str,
    keyword_name: str,
) -> list[tuple[int, str]]:
    values: list[tuple[int, str]] = []

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue

        if ast.unparse(node.func) != function_name:
            continue

        for keyword in node.keywords:
            if keyword.arg != keyword_name:
                continue

            values.append(
                (
                    node.lineno,
                    ast.unparse(keyword.value),
                )
            )

    return values


def test_trade_validator_daily_limit_is_not_static_false():
    values = _keyword_values(
        function_name=(
            "self.trade_validator_v2.validate"
        ),
        keyword_name="daily_limit_reached",
    )

    assert len(values) == 1

    _, expression = values[0]

    assert expression != "False"


def test_trade_validator_daily_limit_uses_runtime_authority():
    values = _keyword_values(
        function_name=(
            "self.trade_validator_v2.validate"
        ),
        keyword_name="daily_limit_reached",
    )

    assert len(values) == 1

    _, expression = values[0]

    assert (
        "daily_limit" in expression
        or "account_risk" in expression
    )


def test_account_risk_daily_limit_reason_exists_before_validator():
    tree = _tree()

    account_risk_line = None
    validator_line = None

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "account_risk"
                ):
                    value = ast.unparse(node.value)

                    if (
                        "self.account_risk_guard.evaluate"
                        in value
                    ):
                        account_risk_line = (
                            node.lineno
                        )

        if isinstance(node, ast.Call):
            if (
                ast.unparse(node.func)
                == "self.trade_validator_v2.validate"
            ):
                validator_line = node.lineno

    assert account_risk_line is not None
    assert validator_line is not None

    assert account_risk_line < validator_line


def test_execution_decision_daily_limit_remains_out_of_scope():
    values = _keyword_values(
        function_name=(
            "self.execution_decision_engine_v2.evaluate"
        ),
        keyword_name="daily_limit_reached",
    )

    assert values == [(2720, "False")]


def test_runtime_daily_loss_limit_reaches_trade_validator(
    monkeypatch,
):
    from datetime import datetime, timedelta, timezone

    from backend.account_risk.account_risk_guard import (
        AccountRiskGuard,
    )
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
    from backend.services.live_analysis_store import (
        LiveAnalysisStore,
    )
    from backend.services.live_candle_store import (
        LiveCandleStore,
    )
    from backend.services.live_market_analysis_service import (
        LiveMarketAnalysisService,
    )
    from backend.services.trade_history_store import (
        TradeHistoryStore,
    )

    class CapturingTradeValidator(
        TradeValidatorV2
    ):
        def __init__(self) -> None:
            super().__init__(
                        minimum_reward_risk_ratio=2.0,
                        minimum_stop_points=2.0,
                        maximum_stop_points=50.0,
                        maximum_spread_points=1.0,
                        minimum_atr_points=3.0,
                        maximum_signal_age_seconds=30,
                    )
            self.daily_limit_reached_seen = None

        def validate(
            self,
            **kwargs,
        ):
            self.daily_limit_reached_seen = kwargs[
                "daily_limit_reached"
            ]
            return super().validate(
                **kwargs,
            )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()
    trade_history_store = TradeHistoryStore()

    base_time = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone.utc,
    )

    from backend.models.candle import Candle

    for index in range(60):
        base = 21600.0 + index * 1.5

        candle_store.add(
            Candle(
                symbol="NQ",
                timeframe="5m",
                open=base,
                high=base + 4.0,
                low=base - 2.0,
                close=base + 2.5,
                volume=1000.0 + index * 10,
                timestamp=(
                    base_time
                    + timedelta(
                        minutes=index * 5
                    )
                ),
            )
        )

    trade_history_store.append(
        {
            "symbol": "NQ",
            "timeframe": "5m",
            "side": "LONG",
            "status": "CLOSED",
            "closed": True,
            "entry_price": 21600.0,
            "exit_price": 21500.0,
            "stop_loss": 21500.0,
            "take_profit": 21800.0,
            "contracts": 1,
            "opened_at": base_time,
            "closed_at": base_time,
            "close_reason": "STOP_LOSS",
            "pnl_points": -100.0,
            "pnl": -3000.0,
        }
    )

    validator = CapturingTradeValidator()

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=AlwaysAcceptExecutionManager(
            cooldown_minutes=15,
        ),
        account_risk_guard=AccountRiskGuard(
            daily_loss_limit=3000.0,
            max_trades_per_day=4,
            max_consecutive_losses=3,
            max_open_positions=1,
            max_risk_per_trade=250.0,
        ),
        trade_history_store=trade_history_store,
        confluence_engine_v2=ConfluenceEngineV2(),
        probability_engine_v2=ProbabilityEngineV2(
            minimum_approval_probability=0.80,
            very_high_threshold=0.90,
            high_threshold=0.80,
            medium_threshold=0.65,
        ),
        execution_decision_engine_v2=ExecutionDecisionEngineV2(
            minimum_probability=0.80,
            minimum_confluence_score=0.80,
        ),
        trade_planner_v2=TradePlannerV2(
            minimum_reward_risk_ratio=2.0,
        ),
        trade_validator_v2=validator,
    )

    monkeypatch.setattr(
        service,
        "_calculate_signal_age_seconds",
        lambda *args, **kwargs: 0,
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

    assert result["account_risk"]["approved"] is False
    assert (
        "daily_loss_limit"
        in result["account_risk"]["reasons"]
    )

    assert "trade_validation_v2" in result
    assert validator.daily_limit_reached_seen is True

    validation = result[
        "trade_validation_v2"
    ]

    assert (
        "daily_limit_reached"
        in validation["blocking_reasons"]
    )
    assert validation["approved"] is False
    assert validation["decision"] == "BLOCK"


def test_runtime_other_account_risk_rejection_does_not_imply_daily_limit(
    monkeypatch,
):
    from datetime import datetime, timedelta, timezone

    from backend.account_risk.account_risk_guard import (
        AccountRiskGuard,
    )
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
    from backend.services.live_analysis_store import (
        LiveAnalysisStore,
    )
    from backend.services.live_candle_store import (
        LiveCandleStore,
    )
    from backend.services.live_market_analysis_service import (
        LiveMarketAnalysisService,
    )
    from backend.services.trade_history_store import (
        TradeHistoryStore,
    )

    class CapturingTradeValidator(
        TradeValidatorV2
    ):
        def __init__(self) -> None:
            super().__init__(
                        minimum_reward_risk_ratio=2.0,
                        minimum_stop_points=2.0,
                        maximum_stop_points=50.0,
                        maximum_spread_points=1.0,
                        minimum_atr_points=3.0,
                        maximum_signal_age_seconds=30,
                    )
            self.daily_limit_reached_seen = None

        def validate(
            self,
            **kwargs,
        ):
            self.daily_limit_reached_seen = kwargs[
                "daily_limit_reached"
            ]
            return super().validate(
                **kwargs,
            )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()
    trade_history_store = TradeHistoryStore()

    base_time = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone.utc,
    )

    from backend.models.candle import Candle

    for index in range(60):
        base = 21600.0 + index * 1.5

        candle_store.add(
            Candle(
                symbol="NQ",
                timeframe="5m",
                open=base,
                high=base + 4.0,
                low=base - 2.0,
                close=base + 2.5,
                volume=1000.0 + index * 10,
                timestamp=(
                    base_time
                    + timedelta(
                        minutes=index * 5
                    )
                ),
            )
        )

    for index in range(3):
        trade_history_store.append(
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "side": "LONG",
                "status": "CLOSED",
                "closed": True,
                "entry_price": 21600.0,
                "exit_price": 21599.0,
                "stop_loss": 21500.0,
                "take_profit": 21800.0,
                "contracts": 1,
                "opened_at": base_time,
                "closed_at": (
                    base_time
                    + timedelta(
                        minutes=index,
                    )
                ),
                "close_reason": "STOP_LOSS",
                "pnl_points": -1.0,
                "pnl": -1.0,
            }
        )

    validator = CapturingTradeValidator()

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=AlwaysAcceptExecutionManager(
            cooldown_minutes=15,
        ),
        account_risk_guard=AccountRiskGuard(
            daily_loss_limit=3000.0,
            max_trades_per_day=10,
            max_consecutive_losses=3,
            max_open_positions=1,
            max_risk_per_trade=250.0,
        ),
        trade_history_store=trade_history_store,
        confluence_engine_v2=ConfluenceEngineV2(),
        probability_engine_v2=ProbabilityEngineV2(
            minimum_approval_probability=0.80,
            very_high_threshold=0.90,
            high_threshold=0.80,
            medium_threshold=0.65,
        ),
        execution_decision_engine_v2=ExecutionDecisionEngineV2(
            minimum_probability=0.80,
            minimum_confluence_score=0.80,
        ),
        trade_planner_v2=TradePlannerV2(
            minimum_reward_risk_ratio=2.0,
        ),
        trade_validator_v2=validator,
    )

    monkeypatch.setattr(
        service,
        "_calculate_signal_age_seconds",
        lambda *args, **kwargs: 0,
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

    assert result["account_risk"]["approved"] is False
    assert (
        "max_consecutive_losses"
        in result["account_risk"]["reasons"]
    )
    assert (
        "daily_loss_limit"
        not in result["account_risk"]["reasons"]
    )

    assert "trade_validation_v2" in result
    assert validator.daily_limit_reached_seen is False

    validation = result[
        "trade_validation_v2"
    ]

    assert (
        "daily_limit_reached"
        not in validation["blocking_reasons"]
    )
