from typing import Any

from backend.indicators.atr_engine import ATREngine
from backend.indicators.ema_engine import EMAEngine
from backend.indicators.rsi_engine import RSIEngine


class IndicatorStage:
    """
    Calcula los indicadores técnicos principales de ARMS AI
    usando los datos preparados por la etapa de mercado.
    """

    def __init__(
        self,
        ema_period: int = 50,
        rsi_period: int = 14,
        atr_period: int = 14,
        atr_low_threshold: float = 5.0,
        atr_high_threshold: float = 15.0,
    ) -> None:
        if ema_period <= 0:
            raise ValueError(
                "ema_period debe ser mayor que cero."
            )

        if rsi_period <= 0:
            raise ValueError(
                "rsi_period debe ser mayor que cero."
            )

        if atr_period <= 0:
            raise ValueError(
                "atr_period debe ser mayor que cero."
            )

        if atr_low_threshold < 0:
            raise ValueError(
                "atr_low_threshold no puede ser negativo."
            )

        if atr_high_threshold <= atr_low_threshold:
            raise ValueError(
                "atr_high_threshold debe ser mayor que "
                "atr_low_threshold."
            )

        self.ema_period = ema_period
        self.rsi_period = rsi_period
        self.atr_period = atr_period
        self.atr_low_threshold = atr_low_threshold
        self.atr_high_threshold = atr_high_threshold

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

        ema = EMAEngine(
            period=self.ema_period,
        )
        ema.calculate(close_prices)

        rsi = RSIEngine(
            period=self.rsi_period,
        )
        rsi.calculate(close_prices)

        atr = ATREngine(
            period=self.atr_period,
            low_threshold=self.atr_low_threshold,
            high_threshold=self.atr_high_threshold,
        )
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
