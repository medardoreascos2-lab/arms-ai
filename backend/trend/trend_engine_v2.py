from __future__ import annotations

from math import isfinite

from backend.indicators.ema_engine import (
    EMAEngine,
)


class TrendEngineV2:
    """
    Analiza tendencia usando velas almacenadas
    en LiveCandleStore.

    Combina:

    - EMA rápida
    - EMA lenta
    - posición del precio
    - pendiente reciente
    - separación entre medias
    """

    VALID_DIRECTIONS = {
        "BULLISH",
        "BEARISH",
        "SIDEWAYS",
        "INSUFFICIENT_DATA",
    }

    def __init__(
        self,
        *,
        live_candle_store,
        fast_period: int = 10,
        slow_period: int = 50,
        slope_lookback: int = 5,
        sideways_threshold_percent: float = 0.0005,
    ) -> None:

        if not callable(
            getattr(
                live_candle_store,
                "get_latest",
                None,
            )
        ):
            raise TypeError(
                "live_candle_store debe implementar "
                "get_latest()."
            )

        if (
            not isinstance(
                fast_period,
                int,
            )
            or fast_period <= 1
        ):
            raise ValueError(
                "fast_period debe ser un entero "
                "mayor que 1."
            )

        if (
            not isinstance(
                slow_period,
                int,
            )
            or slow_period <= fast_period
        ):
            raise ValueError(
                "slow_period debe ser mayor "
                "que fast_period."
            )

        if (
            not isinstance(
                slope_lookback,
                int,
            )
            or slope_lookback < 2
        ):
            raise ValueError(
                "slope_lookback debe ser un entero "
                "mayor o igual que 2."
            )

        normalized_threshold = float(
            sideways_threshold_percent
        )

        if (
            not isfinite(
                normalized_threshold
            )
            or normalized_threshold <= 0
        ):
            raise ValueError(
                "sideways_threshold_percent debe "
                "ser mayor que cero."
            )

        self.live_candle_store = (
            live_candle_store
        )

        self.fast_period = fast_period
        self.slow_period = slow_period
        self.slope_lookback = slope_lookback

        self.sideways_threshold_percent = (
            normalized_threshold
        )

    def analyze(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> dict[str, object]:

        normalized_symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        normalized_timeframe = (
            str(timeframe)
            .strip()
            .upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        if not normalized_timeframe:
            raise ValueError(
                "timeframe no puede estar vacío."
            )

        required_candles = max(
            self.slow_period,
            self.slope_lookback,
        )

        candles = (
            self.live_candle_store
            .get_latest(
                symbol=normalized_symbol,
                timeframe=normalized_timeframe,
                limit=required_candles,
            )
        )

        candle_count = len(
            candles
        )

        if candle_count < self.slow_period:
            return {
                "status": (
                    "INSUFFICIENT_DATA"
                ),
                "direction": (
                    "INSUFFICIENT_DATA"
                ),
                "confidence": 0.0,
                "symbol": normalized_symbol,
                "timeframe": (
                    normalized_timeframe
                ),
                "candle_count": candle_count,
                "required_candles": (
                    self.slow_period
                ),
                "current_price": None,
                "fast_ema": None,
                "slow_ema": None,
                "ema_separation_percent": None,
                "slope": None,
                "slope_percent": None,
                "price_above_slow_ema": None,
                "reason": (
                    "not_enough_candles"
                ),
            }

        closes = [
            float(
                candle.close
            )
            for candle in candles
        ]

        if any(
            (
                not isfinite(price)
                or price <= 0
            )
            for price in closes
        ):
            raise ValueError(
                "Las velas contienen precios "
                "de cierre inválidos."
            )

        current_price = closes[-1]

        fast_ema = float(
            EMAEngine(
                period=self.fast_period
            ).calculate(
                closes
            )
        )

        slow_ema = float(
            EMAEngine(
                period=self.slow_period
            ).calculate(
                closes
            )
        )

        slope_prices = closes[
            -self.slope_lookback:
        ]

        slope = (
            slope_prices[-1]
            - slope_prices[0]
        ) / (
            len(slope_prices)
            - 1
        )

        ema_separation_percent = (
            abs(
                fast_ema
                - slow_ema
            )
            / slow_ema
        )

        slope_percent = (
            abs(
                slope
            )
            / slow_ema
        )

        price_above_slow_ema = (
            current_price
            > slow_ema
        )

        threshold = (
            self.sideways_threshold_percent
        )

        bullish_alignment = (
            fast_ema > slow_ema
            and current_price > slow_ema
            and slope > 0
        )

        bearish_alignment = (
            fast_ema < slow_ema
            and current_price < slow_ema
            and slope < 0
        )

        weak_movement = (
            ema_separation_percent
            < threshold
            and slope_percent
            < threshold
        )

        if weak_movement:
            direction = "SIDEWAYS"

        elif bullish_alignment:
            direction = "BULLISH"

        elif bearish_alignment:
            direction = "BEARISH"

        else:
            direction = "SIDEWAYS"

        separation_score = min(
            ema_separation_percent
            / (
                threshold
                * 4.0
            ),
            1.0,
        )

        slope_score = min(
            slope_percent
            / threshold,
            1.0,
        )

        if direction in {
            "BULLISH",
            "BEARISH",
        }:
            alignment_score = 1.0

            confidence = (
                separation_score
                * 0.45
                + slope_score
                * 0.35
                + alignment_score
                * 0.20
            )

        else:
            movement_strength = max(
                separation_score,
                slope_score,
            )

            confidence = (
                1.0
                - movement_strength
            )

        confidence = round(
            max(
                0.0,
                min(
                    confidence,
                    1.0,
                ),
            ),
            4,
        )

        result = {
            "status": "READY",
            "direction": direction,
            "confidence": confidence,
            "symbol": normalized_symbol,
            "timeframe": normalized_timeframe,
            "candle_count": candle_count,
            "required_candles": (
                self.slow_period
            ),
            "current_price": round(
                current_price,
                10,
            ),
            "fast_ema": round(
                fast_ema,
                10,
            ),
            "slow_ema": round(
                slow_ema,
                10,
            ),
            "ema_separation_percent": round(
                ema_separation_percent,
                10,
            ),
            "slope": round(
                slope,
                10,
            ),
            "slope_percent": round(
                slope_percent,
                10,
            ),
            "price_above_slow_ema": (
                price_above_slow_ema
            ),
            "reason": None,
        }

        if (
            result["direction"]
            not in self.VALID_DIRECTIONS
        ):
            raise RuntimeError(
                "TrendEngineV2 produjo una "
                "dirección inválida."
            )

        return result
