from __future__ import annotations

from backend.market_analysis.market_regime_engine import (
    MarketRegimeEngine,
)

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
from backend.intelligence.confluence_engine_v2 import (
    ConfluenceEngineV2,
)
from backend.intelligence.probability_engine_v2 import (
    ProbabilityEngineV2,
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
from backend.smart_money.smart_money_engine_v2 import (
    SmartMoneyEngineV2,
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
        market_regime_engine:
        MarketRegimeEngine
        | None = None,
    
        confluence_engine_v2:
        ConfluenceEngineV2
        | None = None,

        smart_money_engine_v2:
        SmartMoneyEngineV2
        | None = None,
        probability_engine_v2:
        ProbabilityEngineV2
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


        if (
            confluence_engine_v2
            is not None
            and not isinstance(
                confluence_engine_v2,
                ConfluenceEngineV2,
            )
        ):
            raise TypeError(
                "confluence_engine_v2 debe ser "
                "ConfluenceEngineV2."
            )

        self.confluence_engine_v2 = (
            confluence_engine_v2
        )


        if (
            smart_money_engine_v2
            is not None
            and not isinstance(
                smart_money_engine_v2,
                SmartMoneyEngineV2,
            )
        ):
            raise TypeError(
                "smart_money_engine_v2 debe ser "
                "SmartMoneyEngineV2."
            )

        self.smart_money_engine_v2 = (
            smart_money_engine_v2
        )


        if (
            probability_engine_v2
            is not None
            and not isinstance(
                probability_engine_v2,
                ProbabilityEngineV2,
            )
        ):
            raise TypeError(
                "probability_engine_v2 debe ser "
                "ProbabilityEngineV2."
            )

        self.probability_engine_v2 = (
            probability_engine_v2
        )

        if (
            market_regime_engine
            is not None
            and not isinstance(
                market_regime_engine,
                MarketRegimeEngine,
            )
        ):
            raise TypeError(
                "market_regime_engine debe ser "
                "MarketRegimeEngine."
            )

        self.market_regime_engine = (
            market_regime_engine
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

    def _evaluate_market_regime(
        self,
        candles: list[object],
    ) -> dict[str, object]:
        if self.market_regime_engine is None:
            raise RuntimeError(
                "MarketRegimeEngine "
                "no está configurado."
            )

        closes = [
            float(
                getattr(
                    candle,
                    "close",
                )
            )
            for candle in candles
        ]

        highs = [
            float(
                getattr(
                    candle,
                    "high",
                )
            )
            for candle in candles
        ]

        lows = [
            float(
                getattr(
                    candle,
                    "low",
                )
            )
            for candle in candles
        ]

        if len(closes) < 2:
            directional_strength = 0.0
        else:
            net_movement = (
                closes[-1]
                - closes[0]
            )

            total_movement = sum(
                abs(
                    current
                    - previous
                )
                for previous, current
                in zip(
                    closes,
                    closes[1:],
                )
            )

            if total_movement <= 0:
                directional_strength = 0.0
            else:
                directional_strength = (
                    net_movement
                    / total_movement
                )

        directional_strength = min(
            1.0,
            max(
                -1.0,
                directional_strength,
            ),
        )

        average_price = (
            sum(closes)
            / len(closes)
        )

        average_range = (
            sum(
                high - low
                for high, low
                in zip(
                    highs,
                    lows,
                )
            )
            / len(closes)
        )

        if average_price <= 0:
            volatility_score = 0.0
        else:
            volatility_score = (
                average_range
                / average_price
                * 1000.0
            )

        volatility_score = min(
            1.0,
            max(
                0.0,
                volatility_score,
            ),
        )

        complete_range = (
            max(highs)
            - min(lows)
        )

        recent_window = min(
            10,
            len(candles),
        )

        recent_range = (
            max(
                highs[-recent_window:]
            )
            - min(
                lows[-recent_window:]
            )
        )

        if complete_range <= 0:
            compression_score = 1.0
        else:
            compression_score = (
                1.0
                - min(
                    1.0,
                    recent_range
                    / complete_range,
                )
            )

        compression_score = min(
            1.0,
            max(
                0.0,
                compression_score,
            ),
        )

        regime = (
            self.market_regime_engine.evaluate(
                directional_strength=(
                    directional_strength
                ),
                volatility_score=(
                    volatility_score
                ),
                compression_score=(
                    compression_score
                ),
            )
        )

        return {
            **regime,
            "directional_strength": (
                directional_strength
            ),
            "volatility_score": (
                volatility_score
            ),
            "compression_score": (
                compression_score
            ),
        }


    def _evaluate_confluence_v2(
        self,
        *,
        result: dict[str, object],
        candles: list[object],
        risk_approved: bool,
        sizing_approved: bool,
        market_regime_result:
        dict[str, object]
        | None,
    ) -> dict[str, object]:
        if self.confluence_engine_v2 is None:
            raise RuntimeError(
                "ConfluenceEngineV2 "
                "no está configurado."
            )

        trend_text = str(
            result.get(
                "trend",
                "",
            )
        ).strip().upper()

        trend_score = (
            1.0
            if trend_text in {
                "ALCISTA",
                "BAJISTA",
                "BULLISH",
                "BEARISH",
            }
            else 0.50
        )

        smart_money_data = (
            result.get(
                "smart_money_v2"
            )
        )

        if (
            self.smart_money_engine_v2
            is not None
        ):
            smart_money_data = (
                self._evaluate_smart_money_v2(
                    candles
                )
            )

            result["smart_money_v2"] = (
                smart_money_data
            )

        if isinstance(
            smart_money_data,
            dict,
        ):
            smart_structure = (
                smart_money_data.get(
                    "structure",
                    {},
                )
            )

            smart_fvg = (
                smart_money_data.get(
                    "fvg",
                    {},
                )
            )

            smart_order_block = (
                smart_money_data.get(
                    "order_block",
                    {},
                )
            )

            smart_equal_levels = (
                smart_money_data.get(
                    "equal_levels",
                    {},
                )
            )

            has_structure_confirmation = bool(
                smart_structure.get(
                    "bos",
                    False,
                )
                or smart_structure.get(
                    "choch",
                    False,
                )
                or smart_order_block.get(
                    "order_block",
                    False,
                )
            )

            has_liquidity_confirmation = bool(
                smart_structure.get(
                    "liquidity_sweep",
                    False,
                )
                or smart_equal_levels.get(
                    "equal_highs",
                    False,
                )
                or smart_equal_levels.get(
                    "equal_lows",
                    False,
                )
            )

            has_fvg_confirmation = bool(
                smart_fvg.get(
                    "fvg",
                    False,
                )
            )

            structure_score = (
                1.0
                if has_structure_confirmation
                else 0.50
            )

            liquidity_score = (
                1.0
                if has_liquidity_confirmation
                else 0.50
            )

            fvg_score = (
                1.0
                if has_fvg_confirmation
                else 0.50
            )

        else:
            structure_score = (
                1.0
                if (
                    result.get(
                        "market_structure"
                    )
                    or result.get(
                        "structure"
                    )
                )
                else 0.50
            )

            liquidity_score = (
                1.0
                if (
                    result.get(
                        "liquidity"
                    )
                    or result.get(
                        "liquidity_analysis"
                    )
                )
                else 0.50
            )

            fvg_score = (
                1.0
                if (
                    result.get(
                        "fvg"
                    )
                    or result.get(
                        "fair_value_gap"
                    )
                )
                else 0.50
            )

        ema_alignment_score = (
            1.0
            if (
                result.get(
                    "ema"
                )
                or result.get(
                    "ema_alignment"
                )
            )
            else 0.50
        )

        probability_data = (
            result.get(
                "probability"
            )
            or result.get(
                "confidence"
            )
            or 0.50
        )

        if isinstance(
            probability_data,
            dict,
        ):
            probability_data = (
                probability_data.get(
                    "probability",
                    probability_data.get(
                        "confidence",
                        0.50,
                    ),
                )
            )

        try:
            probability_score = float(
                probability_data
            )
        except (
            TypeError,
            ValueError,
        ):
            probability_score = 0.50

        if probability_score > 1.0:
            probability_score = (
                probability_score
                / 100.0
            )

        probability_score = min(
            1.0,
            max(
                0.0,
                probability_score,
            ),
        )

        if market_regime_result is None:
            market_regime_score = 0.50
            market_tradable = True
        else:
            market_regime_score = float(
                market_regime_result.get(
                    "confidence",
                    0.50,
                )
            )

            market_regime_score = min(
                1.0,
                max(
                    0.0,
                    market_regime_score,
                ),
            )

            market_tradable = bool(
                market_regime_result.get(
                    "tradable",
                    True,
                )
            )

        volumes = [
            float(
                getattr(
                    candle,
                    "volume",
                    0.0,
                )
            )
            for candle in candles
        ]

        if volumes and sum(
            volumes
        ) > 0:
            average_volume = (
                sum(volumes)
                / len(volumes)
            )

            volume_score = min(
                1.0,
                max(
                    0.0,
                    volumes[-1]
                    / average_volume,
                ),
            )
        else:
            volume_score = 0.50

        return (
            self.confluence_engine_v2
            .evaluate(
                trend_score=trend_score,
                structure_score=(
                    structure_score
                ),
                liquidity_score=(
                    liquidity_score
                ),
                fvg_score=fvg_score,
                ema_alignment_score=(
                    ema_alignment_score
                ),
                market_regime_score=(
                    market_regime_score
                ),
                probability_score=(
                    probability_score
                ),
                volume_score=volume_score,
                risk_approved=risk_approved,
                sizing_approved=(
                    sizing_approved
                ),
                market_tradable=(
                    market_tradable
                ),
            )
        )

    def _evaluate_smart_money_v2(
        self,
        candles: list[object],
    ) -> dict[str, object]:
        if self.smart_money_engine_v2 is None:
            raise RuntimeError(
                "SmartMoneyEngineV2 "
                "no está configurado."
            )

        if len(candles) < 3:
            raise ValueError(
                "Se requieren al menos "
                "tres velas."
            )

        first = candles[-3]
        second = candles[-2]
        third = candles[-1]

        first_open = float(
            getattr(
                first,
                "open",
            )
        )
        first_high = float(
            getattr(
                first,
                "high",
            )
        )
        first_low = float(
            getattr(
                first,
                "low",
            )
        )
        first_close = float(
            getattr(
                first,
                "close",
            )
        )

        second_open = float(
            getattr(
                second,
                "open",
            )
        )
        second_high = float(
            getattr(
                second,
                "high",
            )
        )
        second_low = float(
            getattr(
                second,
                "low",
            )
        )
        second_close = float(
            getattr(
                second,
                "close",
            )
        )

        third_high = float(
            getattr(
                third,
                "high",
            )
        )
        third_low = float(
            getattr(
                third,
                "low",
            )
        )
        third_close = float(
            getattr(
                third,
                "close",
            )
        )

        previous_direction = None

        if second_close > second_open:
            previous_direction = "BULLISH"
        elif second_close < second_open:
            previous_direction = "BEARISH"

        structure = (
            self.smart_money_engine_v2
            .evaluate(
                previous_high=second_high,
                previous_low=second_low,
                current_high=third_high,
                current_low=third_low,
                close_price=third_close,
                previous_direction=(
                    previous_direction
                ),
            )
        )

        fvg = (
            self.smart_money_engine_v2
            .detect_fvg(
                first_high=first_high,
                first_low=first_low,
                second_high=second_high,
                second_low=second_low,
                third_high=third_high,
                third_low=third_low,
            )
        )

        impulse_direction = (
            structure["direction"]
            if structure["direction"]
            in {
                "BULLISH",
                "BEARISH",
            }
            else (
                previous_direction
                or (
                    "BULLISH"
                    if first_close
                    >= first_open
                    else "BEARISH"
                )
            )
        )

        order_block = (
            self.smart_money_engine_v2
            .detect_order_block(
                candle_open=second_open,
                candle_high=second_high,
                candle_low=second_low,
                candle_close=second_close,
                impulse_direction=(
                    impulse_direction
                ),
            )
        )

        range_high = max(
            float(
                getattr(
                    candle,
                    "high",
                )
            )
            for candle in candles
        )

        range_low = min(
            float(
                getattr(
                    candle,
                    "low",
                )
            )
            for candle in candles
        )

        price_zone = (
            self.smart_money_engine_v2
            .evaluate_price_zone(
                range_high=range_high,
                range_low=range_low,
                current_price=third_close,
            )
        )

        equal_levels = (
            self.smart_money_engine_v2
            .detect_equal_levels(
                first_high=second_high,
                second_high=third_high,
                first_low=second_low,
                second_low=third_low,
                tolerance=0.25,
            )
        )

        return {
            "structure": structure,
            "fvg": fvg,
            "order_block": (
                order_block
            ),
            "price_zone": (
                price_zone
            ),
            "equal_levels": (
                equal_levels
            ),
        }


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

        market_regime_result = None

        if (
            self.market_regime_engine
            is not None
        ):
            market_regime_result = (
                self._evaluate_market_regime(
                    candles
                )
            )

            result["market_regime"] = (
                market_regime_result
            )

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
                            market_tradable=(
                                bool(
                                    market_regime_result[
                                        "tradable"
                                    ]
                                )
                                if market_regime_result
                                is not None
                                else None
                            ),
                            market_regime=(
                                str(
                                    market_regime_result[
                                        "regime"
                                    ]
                                )
                                if market_regime_result
                                is not None
                                else None
                            ),
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

        if (
            self.confluence_engine_v2
            is not None
        ):
            confluence_v2_result = (
                self._evaluate_confluence_v2(
                    result=result,
                    candles=candles,
                    risk_approved=True,
                    sizing_approved=True,
                    market_regime_result=(
                        locals().get(
                            "market_regime_result"
                        )
                    ),
                )
            )

            result["confluence_v2"] = (
                confluence_v2_result
            )

        if (
            self.smart_money_engine_v2
            is not None
        ):
            result["smart_money_v2"] = (
                self._evaluate_smart_money_v2(
                    candles
                )
            )


        if (
            self.probability_engine_v2
            is not None
        ):
            smart_money = result.get(
                "smart_money_v2",
                {},
            )

            confluence = result.get(
                "confluence_v2",
                {},
            )

            market_regime = result.get(
                "market_regime",
                {},
            )

            trend_score = (
                1.0
                if result.get(
                    "trend"
                )
                in {
                    "ALCISTA",
                    "BAJISTA",
                }
                else 0.50
            )

            smart_money_score = (
                confluence.get(
                    "structure_score",
                    0.50,
                )
            )

            raw_confluence_score = float(
                confluence.get(
                    "score",
                    50.0,
                )
            )

            confluence_score = round(
                (
                    raw_confluence_score
                    / 100.0
                    if raw_confluence_score
                    > 1.0
                    else raw_confluence_score
                ),
                4,
            )

            market_regime_score = (
                market_regime.get(
                    "confidence",
                    0.50,
                )
            )

            volume_score = (
                1.0
                if result.get(
                    "volume"
                )
                else 0.50
            )

            result[
                "probability_v2"
            ] = (
                self.probability_engine_v2.evaluate(
                    smart_money_score=smart_money_score,
                    trend_score=trend_score,
                    market_regime_score=market_regime_score,
                    confluence_score=confluence_score,
                    volume_score=volume_score,
                    risk_approved=True,
                    sizing_approved=True,
                    market_tradable=market_regime.get(
                        "tradable",
                        True,
                    ),
                )
            )

        return result
