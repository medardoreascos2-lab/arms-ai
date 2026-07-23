from __future__ import annotations

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
from backend.services.live_analysis_store import (
    LiveAnalysisStore,
)
from backend.execution.signal_execution_manager import (
    SignalExecutionManager,
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
            result["execution"] = (
                self.execution_manager.evaluate(
                    signal
                )
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
