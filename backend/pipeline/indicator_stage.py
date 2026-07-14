from typing import Any

from backend.indicators.atr_engine import ATREngine
from backend.indicators.ema_engine import EMAEngine
from backend.indicators.rsi_engine import RSIEngine


class IndicatorStage:
    """
    Calcula los indicadores técnicos principales de ARMS AI
    usando los datos preparados por MarketStage.
    """

    def __init__(
        self,
        ema_period: int = 50,
        rsi_period: int = 14,
        atr_period: int = 14,
    ) -> None:
        self.ema_period = ema_period
        self.rsi_period = rsi_period
        self.atr_period = atr_period

    def run(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        if "candle_manager" not in context:
            raise KeyError(
                "IndicatorStage requiere 'candle_manager'."
            )

        if "candles" not in context:
            raise KeyError(
                "IndicatorStage requiere 'candles'."
            )

        candle_manager = context["candle_manager"]
        candles = context["candles"]

        close_prices = candle_manager.get_close_prices()

        ema = EMAEngine(period=self.ema_period)
        ema.calculate(close_prices)

        rsi = RSIEngine(period=self.rsi_period)
        rsi.calculate(close_prices)

        atr = ATREngine(period=self.atr_period)
        atr.calculate(candles)

        context.update(
            {
                "close_prices": close_prices,
                "ema": ema,
                "rsi": rsi,
                "atr": atr,
            }
        )

        return context
