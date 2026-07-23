from __future__ import annotations

from backend.account_risk.account_risk_guard import (
    AccountRiskGuard,
)
from backend.ai.trading.trading_copilot_service import (
    TradingCopilotService,
)
from backend.pipeline.arms_pipeline import (
    ArmsPipeline,
)
from backend.pipeline.backtest_market_stage import (
    BacktestMarketStage,
)
from backend.pipeline.decision_stage import (
    DecisionStage,
)
from backend.pipeline.indicator_stage import (
    IndicatorStage,
)
from backend.pipeline.intelligence_stage import (
    IntelligenceStage,
)
from backend.pipeline.risk_stage import (
    RiskStage,
)
from backend.pipeline.smart_money_stage import (
    SmartMoneyStage,
)
from backend.services.executable_signal_store import (
    ExecutableSignalStore,
)
from backend.services.live_analysis_store import (
    LiveAnalysisStore,
)
from backend.execution.signal_execution_manager import (
    SignalExecutionManager,
)
from backend.execution.execution_decision_engine import (
    ExecutionDecisionEngine,
)
from backend.execution.trade_execution_engine import (
    TradeExecutionEngine,
)
from backend.execution.position_manager import (
    PositionManager,
)
from backend.signals.signal_engine import (
    SignalEngine,
)
from backend.services.live_candle_store import (
    LiveCandleStore,
)
from backend.services.live_signal_store import (
    LiveSignalStore,
)
from backend.services.signal_history_store import (
    SignalHistoryStore,
)
from backend.risk_management.position_sizing_engine import (
    PositionSizingEngine,
)
from backend.services.trade_history_store import (
    TradeHistoryStore,
)


class LiveMarketAnalysisService:
    MINIMUM_CANDLES = 50

    def __init__(
        self,
        *,
        candle_store: LiveCandleStore,
        analysis_store: LiveAnalysisStore,
        signal_store: LiveSignalStore
        | None = None,
        signal_history_store: SignalHistoryStore
        | None = None,
        execution_manager:
        SignalExecutionManager
        | None = None,
        executable_signal_store:
        ExecutableSignalStore
        | None = None,
        trade_execution_engine:
        TradeExecutionEngine
        | None = None,
        position_manager:
        PositionManager
        | None = None,
        account_risk_guard:
        AccountRiskGuard
        | None = None,
        trade_history_store:
        TradeHistoryStore
        | None = None,
        position_sizing_engine:
        PositionSizingEngine
        | None = None,
        execution_decision_engine:
        ExecutionDecisionEngine
        | None = None,
    ) -> None:
        self.candle_store = candle_store
        self.analysis_store = analysis_store
        self.signal_store = signal_store
        self.signal_history_store = (
            signal_history_store
        )
        self.execution_manager = (
            execution_manager
        )
        self.executable_signal_store = (
            executable_signal_store
        )
        self.trade_execution_engine = (
            trade_execution_engine
        )
        self.position_manager = (
            position_manager
        )
        self.account_risk_guard = (
            account_risk_guard
        )
        self.trade_history_store = (
            trade_history_store
        )
        self.position_sizing_engine = (
            position_sizing_engine
        )

        if (
            execution_decision_engine
            is not None
            and not isinstance(
                execution_decision_engine,
                ExecutionDecisionEngine,
            )
        ):
            raise TypeError(
                "execution_decision_engine debe ser "
                "ExecutionDecisionEngine."
            )

        self.execution_decision_engine = (
            execution_decision_engine
        )

    def can_analyze(
        self,
        *,
        symbol: str,
        timeframe: str,
        minimum_candles: int | None = None,
    ) -> bool:
        required = (
            minimum_candles
            or self.MINIMUM_CANDLES
        )

        return (
            self.candle_store.count(
                symbol=symbol,
                timeframe=timeframe,
            )
            >= required
        )

    def analyze(
        self,
        *,
        symbol: str,
        timeframe: str,
        candle_limit: int,
        account_balance: float,
        risk_percent: float,
        point_value: float,
        reward_risk_ratio: float,
    ) -> dict[str, object]:
        candles = self.candle_store.get_latest(
            symbol=symbol,
            timeframe=timeframe,
            limit=candle_limit,
        )

        if len(candles) < self.MINIMUM_CANDLES:
            raise ValueError(
                "No existen suficientes velas para analizar."
            )

        pipeline = ArmsPipeline(
            stages=[
                BacktestMarketStage(
                    max_candles=max(
                        500,
                        len(candles),
                    ),
                ),
                IndicatorStage(),
                SmartMoneyStage(),
                IntelligenceStage(),
                RiskStage(
                    account_balance=account_balance,
                    risk_percent=risk_percent,
                    reward_risk_ratio=reward_risk_ratio,
                    point_value=point_value,
                ),
                DecisionStage(
                    reward_risk_ratio=reward_risk_ratio,
                ),
            ]
        )

        context = pipeline.run(
            initial_context={
                "symbol": symbol,
                "timeframe": timeframe,
                "backtest_candles": candles,
            }
        )

        result = TradingCopilotService().build_context(
            context
        )

        result["analyzed_at"] = (
            candles[-1].timestamp
        )

        signal = SignalEngine().generate(
            result
        )

        signal["generated_at"] = (
            result["analyzed_at"]
        )

        result["signal"] = signal

        if (
            self.execution_manager
            is not None
        ):
            execution = (
                self.execution_manager.evaluate(
                    signal
                )
            )

            result["execution"] = execution

            if (
                execution["accepted"]
            ):
                position_sizing_approved = True

                if (
                    self.position_sizing_engine
                    is not None
                ):
                    position_sizing = (
                        self.position_sizing_engine.calculate(
                            account_balance=account_balance,
                            risk_percent=risk_percent,
                            entry_price=float(
                                execution["entry_price"]
                            ),
                            stop_loss=float(
                                execution["stop_loss"]
                            ),
                            point_value=point_value,
                        )
                    )

                    result["position_sizing"] = (
                        position_sizing
                    )

                    position_sizing_approved = bool(
                        position_sizing["approved"]
                    )

                    if position_sizing_approved:
                        execution["contracts"] = int(
                            position_sizing["contracts"]
                        )

                account_risk_approved = True

                if (
                    self.account_risk_guard
                    is not None
                ):
                    open_positions = 0

                    if (
                        self.position_manager
                        is not None
                        and self.position_manager.get_open_position(
                            symbol=symbol,
                            timeframe=timeframe,
                        )
                        is not None
                    ):
                        open_positions = 1

                    proposed_risk = (
                        account_balance
                        * risk_percent
                        / 100.0
                    )

                    trades_today: list[
                        dict[str, object]
                    ] = []

                    if (
                        self.trade_history_store
                        is not None
                    ):
                        history = (
                            self.trade_history_store.get_history(
                                symbol=symbol,
                                timeframe=timeframe,
                                limit=500,
                            )
                        )

                        analysis_date = (
                            result["analyzed_at"].date()
                        )

                        trades_today = [
                            trade
                            for trade in history
                            if trade["closed_at"].date()
                            == analysis_date
                        ]

                    account_risk = (
                        self.account_risk_guard.evaluate(
                            trades_today=trades_today,
                            open_positions=open_positions,
                            proposed_risk=proposed_risk,
                        )
                    )

                    result["account_risk"] = (
                        account_risk
                    )

                    account_risk_approved = bool(
                        account_risk["approved"]
                    )

                execution_decision_approved = (
                    position_sizing_approved
                    and account_risk_approved
                )

                if (
                    self.execution_decision_engine
                    is not None
                ):
                    raw_confidence = float(
                        execution.get(
                            "confidence",
                            0.0,
                        )
                    )

                    if raw_confidence > 1.0:
                        raw_confidence = (
                            raw_confidence
                            / 100.0
                        )

                    raw_confidence = min(
                        1.0,
                        max(
                            0.0,
                            raw_confidence,
                        ),
                    )

                    contracts = int(
                        execution.get(
                            "contracts",
                            0,
                        )
                    )

                    execution_decision = (
                        self.execution_decision_engine
                        .evaluate(
                            signal_accepted=bool(
                                execution["accepted"]
                            ),
                            signal_confidence=(
                                raw_confidence
                            ),
                            risk_approved=(
                                account_risk_approved
                            ),
                            sizing_approved=(
                                position_sizing_approved
                            ),
                            contracts=contracts,
                        )
                    )

                    result["execution_decision"] = (
                        execution_decision
                    )

                    execution_decision_approved = bool(
                        execution_decision[
                            "approved"
                        ]
                    )

                if execution_decision_approved:
                    if (
                        self.executable_signal_store
                        is not None
                    ):
                        self.executable_signal_store.save(
                            execution
                        )

                    if (
                        self.trade_execution_engine
                        is not None
                    ):
                        trade = (
                            self.trade_execution_engine.execute(
                                execution
                            )
                        )

                        result["trade_execution"] = trade

                        if (
                            self.position_manager
                            is not None
                        ):
                            try:
                                result["position"] = (
                                    self.position_manager.open_position(
                                        trade
                                    )
                                )
                            except ValueError as exc:
                                result["position_error"] = (
                                    str(exc)
                                )

        if self.signal_store is not None:
            self.signal_store.save(
                signal
            )

        if (
            self.signal_history_store
            is not None
        ):
            self.signal_history_store.append(
                signal
            )

        self.analysis_store.save(
            result
        )

        return result
