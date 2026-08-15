from __future__ import annotations

from backend.intelligence.confluence_engine import (
    ConfluenceEngine,
)

from backend.intelligence.probability_engine import (
    ProbabilityEngine,
)

from backend.smart_money.market_structure import (
    MarketStructureEngine,
)

from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)


class ArmsIntelligentStrategyV2:
    """
    Estrategia inteligente de ARMS AI.

    Une:
    - estructura de mercado
    - confluencia
    - probabilidad
    """

    def __init__(
        self,
        *,
        ema: int = 50,
    ) -> None:

        self.ema = ema

        self.market_structure = (
            MarketStructureEngine()
        )

        self.confluence_engine = (
            ConfluenceEngine()
        )

        self.probability_engine = (
            ProbabilityEngine()
        )


    def run(
        self,
        context,
    ) -> TradingDecisionV2:

        candles = context.get(
            "historical_candles",
            []
        )

        candle = context.get(
            "candle",
            {}
        )


        if len(candles) < 3:
            return TradingDecisionV2(
                action=TradingActionV2.HOLD,
                confidence=0.0,
                reason="INSUFFICIENT_DATA",
            )


        structure = (
            self.market_structure
            .analyze(candles)
        )


        if structure == "ALCISTA":

            trend = "BUY"
            ema = "BUY"

        elif structure == "BAJISTA":

            trend = "SELL"
            ema = "SELL"

        else:

            trend = "NEUTRAL"
            ema = "NEUTRAL"


        confluence = (
            self.confluence_engine.evaluate(
                trend=trend,
                ema=ema,
                rsi="BUY",
                atr="GOOD",
                structure=structure,
                bos=trend,
                choch=trend,
                liquidity="BUY",
                risk="APPROVED",
            )
        )


        probability = (
            self.probability_engine.evaluate(
                confluence
            )
        )


        if not probability.approved:

            return TradingDecisionV2(
                action=TradingActionV2.HOLD,
                confidence=(
                    probability.probability
                    / 100
                ),
                reason=(
                    "NO_TRADE "
                    + probability.recommendation
                ),
                metadata={
                    "confluence_score": (
                        confluence.score
                        / 100
                    ),
                    "grade": confluence.grade,
                },
            )


        entry = float(
            candle.get(
                "close",
                0
            )
        )


        if confluence.direction == "BUY":

            action = TradingActionV2.BUY

            stop_loss = entry - 50
            take_profit = entry + 100


        else:

            action = TradingActionV2.SELL

            stop_loss = entry + 50
            take_profit = entry - 100


        return TradingDecisionV2(
            action=action,
            confidence=(
                probability.probability
                / 100
            ),
            reason="ARMS AI CONFIRMED",
            metadata={
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "contracts": 2,
                "confluence_score": (
                    confluence.score
                    / 100
                ),
                "grade": confluence.grade,
            },
        )
