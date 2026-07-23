from __future__ import annotations


class MarketRegimeEngine:
    """
    Clasifica el régimen actual del mercado
    usando fuerza direccional, volatilidad
    y compresión.
    """

    def __init__(
        self,
        *,
        trend_threshold: float,
        high_volatility_threshold: float,
        low_volatility_threshold: float,
        compression_threshold: float,
    ) -> None:
        normalized_trend_threshold = float(
            trend_threshold
        )

        normalized_high_volatility = float(
            high_volatility_threshold
        )

        normalized_low_volatility = float(
            low_volatility_threshold
        )

        normalized_compression = float(
            compression_threshold
        )

        if not (
            0.0
            <= normalized_trend_threshold
            <= 1.0
        ):
            raise ValueError(
                "trend_threshold debe estar "
                "entre 0 y 1."
            )

        if not (
            0.0
            <= normalized_low_volatility
            <= 1.0
        ):
            raise ValueError(
                "low_volatility_threshold debe "
                "estar entre 0 y 1."
            )

        if not (
            0.0
            <= normalized_high_volatility
            <= 1.0
        ):
            raise ValueError(
                "high_volatility_threshold debe "
                "estar entre 0 y 1."
            )

        if (
            normalized_low_volatility
            >= normalized_high_volatility
        ):
            raise ValueError(
                "Los umbrales de volatility "
                "están en un orden inválido."
            )

        if not (
            0.0
            <= normalized_compression
            <= 1.0
        ):
            raise ValueError(
                "compression_threshold debe estar "
                "entre 0 y 1."
            )

        self.trend_threshold = (
            normalized_trend_threshold
        )

        self.high_volatility_threshold = (
            normalized_high_volatility
        )

        self.low_volatility_threshold = (
            normalized_low_volatility
        )

        self.compression_threshold = (
            normalized_compression
        )

    def evaluate(
        self,
        *,
        directional_strength: float,
        volatility_score: float,
        compression_score: float,
    ) -> dict[str, object]:
        direction = float(
            directional_strength
        )

        volatility = float(
            volatility_score
        )

        compression = float(
            compression_score
        )

        if not (
            -1.0
            <= direction
            <= 1.0
        ):
            raise ValueError(
                "directional_strength debe estar "
                "entre -1 y 1."
            )

        if not (
            0.0
            <= volatility
            <= 1.0
        ):
            raise ValueError(
                "volatility_score debe estar "
                "entre 0 y 1."
            )

        if not (
            0.0
            <= compression
            <= 1.0
        ):
            raise ValueError(
                "compression_score debe estar "
                "entre 0 y 1."
            )

        confidence = min(
            1.0,
            max(
                0.0,
                abs(direction),
            ),
        )

        if compression >= (
            1.0
            - self.compression_threshold
        ):
            return {
                "regime": "NO_TRADE",
                "tradable": False,
                "direction": "NEUTRAL",
                "confidence": compression,
                "risk_multiplier": 0.0,
            }

        if (
            volatility
            >= self.high_volatility_threshold
        ):
            return {
                "regime": "HIGH_VOLATILITY",
                "tradable": True,
                "direction": "NEUTRAL",
                "confidence": volatility,
                "risk_multiplier": 0.50,
            }

        if (
            volatility
            <= self.low_volatility_threshold
        ):
            return {
                "regime": "LOW_VOLATILITY",
                "tradable": False,
                "direction": "NEUTRAL",
                "confidence": (
                    1.0 - volatility
                ),
                "risk_multiplier": 0.0,
            }

        if (
            direction
            >= self.trend_threshold
        ):
            return {
                "regime": "TREND_UP",
                "tradable": True,
                "direction": "LONG",
                "confidence": confidence,
                "risk_multiplier": 1.0,
            }

        if (
            direction
            <= -self.trend_threshold
        ):
            return {
                "regime": "TREND_DOWN",
                "tradable": True,
                "direction": "SHORT",
                "confidence": confidence,
                "risk_multiplier": 1.0,
            }

        return {
            "regime": "RANGE",
            "tradable": True,
            "direction": "NEUTRAL",
            "confidence": (
                1.0 - confidence
            ),
            "risk_multiplier": 0.75,
        }
