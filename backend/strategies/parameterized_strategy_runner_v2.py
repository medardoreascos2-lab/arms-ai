from __future__ import annotations

from backend.indicators.ema_engine import EMAEngine

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


    def run(
        self,
        context,
    ) -> TradingDecisionV2:

        self.calls += 1

        candle = context.get(
            "candle",
            {},
        )

        history = context.get(
            "history",
            [],
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


        if entry_price > ema_value:

            return TradingDecisionV2(
                action=TradingActionV2.BUY,
                confidence=0.85,
                reason=f"PRICE ABOVE EMA {self.ema}",
                metadata={
                    "stop_loss": entry_price - 50,
                    "take_profit": entry_price + 100,
                    "contracts": 2,
                    "confluence_score": 0.85,
                    "grade": "A",
                },
            )


        if entry_price < ema_value:

            return TradingDecisionV2(
                action=TradingActionV2.SELL,
                confidence=0.85,
                reason=f"PRICE BELOW EMA {self.ema}",
                metadata={
                    "stop_loss": entry_price + 50,
                    "take_profit": entry_price - 100,
                    "contracts": 2,
                    "confluence_score": 0.85,
                    "grade": "A",
                },
            )


        return TradingDecisionV2(
            action=TradingActionV2.HOLD,
            confidence=0.5,
            reason="PRICE AT EMA",
        )
