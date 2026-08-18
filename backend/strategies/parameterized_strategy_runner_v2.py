from __future__ import annotations

from backend.indicators.ema_engine import EMAEngine

from backend.market_structure.market_structure_engine_v3 import (
    MarketStructureEngineV3,
)

from backend.trend.trend_context_engine_v2 import (
    TrendContextEngineV2,
)

from backend.intelligence.confluence_engine_v2 import (
    ConfluenceEngineV2,
)

from backend.intelligence.trade_quality_engine_v1 import (
    TradeQualityEngineV1,
)

from backend.intelligence.position_filter_v1 import (
    PositionFilterV1,
)

from backend.execution.position_lifecycle_manager_v1 import (
    PositionLifecycleManagerV1,
)

from backend.risk.signal_controller_v2 import (
    SignalControllerV2,
)

from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)


class ParameterizedStrategyRunnerV2:
    """
    Runner de estrategia parametrizable para optimización.

    Utiliza historial de velas y EMA dinámica.
    """

    def __init__(
        self,
        *,
        ema: int,
    ) -> None:

        self.ema = int(
            ema
        )

        self.calls = 0

        # Estado interno de la estrategia
        self.position_state = "FLAT"

        self.market_structure_engine = (
            MarketStructureEngineV3()
        )

        self.trend_context_engine = (
            TrendContextEngineV2()
        )

        self.confluence_engine = (
            ConfluenceEngineV2()
        )

        self.trade_quality_engine = (
            TradeQualityEngineV1()
        )

        self.position_filter = (
            PositionFilterV1()
        )

        self.position_lifecycle = (
            PositionLifecycleManagerV1()
        )

        self.signal_controller = (
            SignalControllerV2()
        )


    def run(
        self,
        context,
    ) -> TradingDecisionV2:

        self.calls += 1

        candle = context.get(
            "candle",
            {},
        )


        current_price = float(
            candle.get(
                "close",
                0,
            )
        )


        if current_price > 0:

            lifecycle_result = (
                self.position_lifecycle.update(
                    current_price
                )
            )


            if lifecycle_result.closed:

                self.position_state = "FLAT"



        if context.get(
            "has_active_position",
            False,
        ):

            return TradingDecisionV2(
                action=TradingActionV2.HOLD,
                confidence=0.5,
                reason="ACTIVE POSITION",
                metadata={},
            )


        history = context.get(
            "history",
            [],
        )


        market_structure = (
            self.market_structure_engine.analyze(
                history
            )
        )


        candles_15m = context.get(
            "history_15m",
            history,
        )


        candles_1h = context.get(
            "history_1h",
            history,
        )


        trend_context = (
            self.trend_context_engine.analyze(
                candles_1h,
                candles_15m,
            )
        )


        prices = [
            float(
                item["close"]
            )
            for item in history
            if "close" in item
        ]


        if len(prices) < self.ema:

            return TradingDecisionV2(
                action=TradingActionV2.HOLD,
                confidence=0.0,
                reason="NOT ENOUGH DATA FOR EMA",
            )


        ema_engine = EMAEngine(
            period=self.ema
        )

        ema_value = ema_engine.calculate(
            prices
        )


        previous_ema = ema_value


        if len(prices) > self.ema:

            previous_ema = ema_engine.calculate(
                prices[:-1]
            )


        entry_price = float(
            candle.get(
                "close",
                0,
            )
        )


        if entry_price <= 0:

            return TradingDecisionV2(
                action=TradingActionV2.HOLD,
                confidence=0.0,
                reason="NO PRICE",
            )



        bullish_score = 0
        bearish_score = 0


        candle_open = float(
            candle.get(
                "open",
                entry_price,
            )
        )


        # Tendencia EMA
        if entry_price > ema_value:
            bullish_score += 40

        if entry_price < ema_value:
            bearish_score += 40


        # Pendiente EMA
        if ema_value > previous_ema:
            bullish_score += 20

        if ema_value < previous_ema:
            bearish_score += 20


        # Confirmación de vela
        if candle_open < entry_price:
            bullish_score += 20

        if candle_open > entry_price:
            bearish_score += 20


        # Momentum simple
        if len(prices) >= 3:

            previous_price = prices[-3]

            if entry_price > previous_price:
                bullish_score += 20

            if entry_price < previous_price:
                bearish_score += 20




        # Market Structure
        if market_structure.trend == "BULLISH":

            bullish_score += 20


        if market_structure.trend == "BEARISH":

            bearish_score += 20



        # Break Of Structure (BOS)
        if market_structure.bos:

            if market_structure.trend == "BULLISH":

                bullish_score += 10


            if market_structure.trend == "BEARISH":

                bearish_score += 10




        ema_alignment = (
            entry_price > ema_value
            and trend_context.allowed_direction == "LONG"
        ) or (
            entry_price < ema_value
            and trend_context.allowed_direction == "SHORT"
        )


        momentum = False


        if len(prices) >= 3:

            momentum = (
                entry_price > prices[-3]
                or entry_price < prices[-3]
            )


        confluence = (
            self.confluence_engine.evaluate(
                trend_context=trend_context,
                market_structure=market_structure,
                ema_alignment=ema_alignment,
                momentum=momentum,
            )
        )


        trade_quality = (
            self.trade_quality_engine.evaluate(
                confluence=confluence,
                market_structure=market_structure,
                trend_context=trend_context,
            )
        )



        # Trend Context Filter

        if trend_context.allowed_direction == "LONG":

            bearish_score = 0


        elif trend_context.allowed_direction == "SHORT":

            bullish_score = 0


        elif not trend_context.aligned:

            bullish_score -= 20
            bearish_score -= 20




        # ==============================
        # TRADE QUALITY HARD FILTER
        # ==============================

        if not trade_quality.approved:

            quality_reason = (
                trade_quality.reasons[0]
                if trade_quality.reasons
                else "TRADE QUALITY BLOCKED"
            )

            return TradingDecisionV2(
                action=TradingActionV2.HOLD,
                confidence=(
                    trade_quality.score / 100
                ),
                reason=quality_reason,
                metadata={
                    "trade_quality_score": (
                        trade_quality.score / 100
                    ),
                    "trade_quality_reasons": (
                        trade_quality.reasons
                    ),
                    "confluence_score": (
                        confluence.score / 100
                    ),
                    "grade": confluence.grade,
                    "reasons": confluence.reasons,
                },
            )


        # ==============================
        # SIGNAL CONTROLLER FILTER
        # ==============================


        signal_direction = (
            trend_context.allowed_direction
        )


        current_index = len(history)


        signal_check = (
            self.signal_controller.evaluate(
                current_index=current_index,
                direction=signal_direction,
                grade=confluence.grade,
            )
        )


        if not signal_check.allowed:

            return TradingDecisionV2(
                action=TradingActionV2.HOLD,
                confidence=0.5,
                reason=signal_check.reason,
                metadata={},
            )



        # ==============================
        # CONFLUENCE ENGINE FINAL FILTER
        # ==============================


        if (
            confluence.allowed
            and trade_quality.approved
        ):


            position_check = (
                self.position_filter.evaluate(
                    current_position=self.position_state,
                    new_direction=trend_context.allowed_direction,
                )
            )


            if not position_check.allowed:

                return TradingDecisionV2(
                    action=TradingActionV2.HOLD,
                    confidence=0.5,
                    reason=position_check.reason,
                )


            if trend_context.allowed_direction == "LONG":


                self.signal_controller.register_trade(
                    index=current_index,
                    direction="LONG",
                )


                return TradingDecisionV2(
                    action=TradingActionV2.BUY,
                    confidence=(
                        confluence.score / 100
                    ),
                    reason=(
                        f"A+ LONG | {confluence.grade}"
                    ),
                    metadata={
                        "stop_loss": entry_price - 50,
                        "take_profit": entry_price + 100,                        "confluence_score": confluence.score / 100,
                        "grade": confluence.grade,
                        "reasons": confluence.reasons,
                    },
                )



            if trend_context.allowed_direction == "SHORT":


                self.signal_controller.register_trade(
                    index=current_index,
                    direction="SHORT",
                )


                return TradingDecisionV2(
                    action=TradingActionV2.SELL,
                    confidence=(
                        confluence.score / 100
                    ),
                    reason=(
                        f"A+ SHORT | {confluence.grade}"
                    ),
                    metadata={
                        "stop_loss": entry_price + 50,
                        "take_profit": entry_price - 100,                        "confluence_score": confluence.score / 100,
                        "grade": confluence.grade,
                        "reasons": confluence.reasons,
                    },
                )



        return TradingDecisionV2(
            action=TradingActionV2.HOLD,
            confidence=(
                confluence.score / 100
            ),
            reason="NO A+ CONFLUENCE",
            metadata={
                "confluence_score": (
                    confluence.score / 100
                ),
                "grade": confluence.grade,
                "reasons": confluence.reasons,
            },
        )
