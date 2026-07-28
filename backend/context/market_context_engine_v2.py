from __future__ import annotations

from math import isfinite
from typing import Any


class MarketContextEngineV2:
    """
    Interpreta la ubicación institucional del precio.

    Combina:

    - rango externo;
    - rango interno;
    - premium, discount y equilibrium;
    - proximidad a extremos;
    - tendencia principal;
    - alineación multitemporal;
    - eventos de Smart Money.

    Contextos posibles:

    - BUY
    - SELL
    - NEUTRAL
    """

    VALID_CONTEXTS = {
        "BUY",
        "SELL",
        "NEUTRAL",
    }

    VALID_DIRECTIONS = {
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
    }

    def __init__(
        self,
        *,
        minimum_candles: int = 5,
        internal_range_lookback: int = 10,
        near_extreme_threshold: float = 0.10,
        equilibrium_tolerance: float = 0.05,
        decision_threshold: float = 0.25,
    ) -> None:
        if (
            not isinstance(
                minimum_candles,
                int,
            )
            or minimum_candles < 3
        ):
            raise ValueError(
                "minimum_candles debe ser "
                "un entero mayor o igual que 3."
            )

        if (
            not isinstance(
                internal_range_lookback,
                int,
            )
            or internal_range_lookback < 3
        ):
            raise ValueError(
                "internal_range_lookback debe "
                "ser un entero mayor o igual que 3."
            )

        self.minimum_candles = minimum_candles

        self.internal_range_lookback = (
            internal_range_lookback
        )

        self.near_extreme_threshold = (
            self._validate_ratio(
                name="near_extreme_threshold",
                value=near_extreme_threshold,
                allow_zero=False,
            )
        )

        self.equilibrium_tolerance = (
            self._validate_ratio(
                name="equilibrium_tolerance",
                value=equilibrium_tolerance,
                allow_zero=True,
            )
        )

        self.decision_threshold = (
            self._validate_ratio(
                name="decision_threshold",
                value=decision_threshold,
                allow_zero=False,
            )
        )

    def analyze(
        self,
        *,
        candles: list[object],
        current_price: float | None = None,
        trend_direction: str = "NEUTRAL",
        multi_timeframe_direction: str = "NEUTRAL",
        smart_money_result: dict[str, object]
        | None = None,
    ) -> dict[str, object]:
        if not isinstance(
            candles,
            list,
        ):
            raise TypeError(
                "candles debe ser una lista."
            )

        if len(candles) < self.minimum_candles:
            return {
                "status": "INSUFFICIENT_DATA",
                "context": "NEUTRAL",
                "context_strength": 0.0,
                "context_score": 0.0,
                "candle_count": len(candles),
                "required_candles": (
                    self.minimum_candles
                ),
                "blocking_reasons": [
                    "insufficient_candle_data"
                ],
                "warnings": [],
            }

        normalized_candles = [
            self._normalize_candle(
                candle
            )
            for candle in candles
        ]

        external_high = max(
            candle["high"]
            for candle in normalized_candles
        )

        external_low = min(
            candle["low"]
            for candle in normalized_candles
        )

        if external_high <= external_low:
            raise ValueError(
                "El rango externo debe tener "
                "una amplitud mayor que cero."
            )

        normalized_price = (
            normalized_candles[-1]["close"]
            if current_price is None
            else self._positive_float(
                "current_price",
                current_price,
            )
        )

        if not (
            external_low
            <= normalized_price
            <= external_high
        ):
            raise ValueError(
                "current_price debe estar dentro "
                "del rango externo."
            )

        internal_candles = normalized_candles[
            -self.internal_range_lookback:
        ]

        internal_high = max(
            candle["high"]
            for candle in internal_candles
        )

        internal_low = min(
            candle["low"]
            for candle in internal_candles
        )

        external_range = self._build_range(
            range_high=external_high,
            range_low=external_low,
            current_price=normalized_price,
        )

        internal_range = self._build_range(
            range_high=internal_high,
            range_low=internal_low,
            current_price=normalized_price,
            allow_outside=True,
        )

        position_ratio = (
            external_range[
                "position_ratio"
            ]
        )

        lower_equilibrium_boundary = (
            0.50
            - self.equilibrium_tolerance
        )

        upper_equilibrium_boundary = (
            0.50
            + self.equilibrium_tolerance
        )

        if (
            position_ratio
            < lower_equilibrium_boundary
        ):
            price_zone = "DISCOUNT"

        elif (
            position_ratio
            > upper_equilibrium_boundary
        ):
            price_zone = "PREMIUM"

        else:
            price_zone = "EQUILIBRIUM"

        near_range_low = (
            position_ratio
            <= self.near_extreme_threshold
        )

        near_range_high = (
            position_ratio
            >= (
                1.0
                - self.near_extreme_threshold
            )
        )

        normalized_trend = (
            self._normalize_direction(
                trend_direction
            )
        )

        normalized_multi = (
            self._normalize_direction(
                multi_timeframe_direction
            )
        )

        trend_alignment = (
            normalized_trend
            == normalized_multi
            and normalized_trend
            in {
                "BULLISH",
                "BEARISH",
            }
        )

        directional_conflict = (
            {
                normalized_trend,
                normalized_multi,
            }
            == {
                "BULLISH",
                "BEARISH",
            }
        )

        smart_money = (
            dict(
                smart_money_result
            )
            if isinstance(
                smart_money_result,
                dict,
            )
            else {}
        )

        smart_money_bias = (
            self._extract_smart_money_bias(
                smart_money
            )
        )

        context_score = (
            self._calculate_context_score(
                trend_direction=(
                    normalized_trend
                ),
                multi_timeframe_direction=(
                    normalized_multi
                ),
                price_zone=price_zone,
                near_range_low=near_range_low,
                near_range_high=near_range_high,
                smart_money_bias=(
                    smart_money_bias
                ),
            )
        )

        blocking_reasons: list[str] = []
        warnings: list[str] = []

        if directional_conflict:
            blocking_reasons.append(
                "trend_timeframe_conflict"
            )

        if price_zone == "EQUILIBRIUM":
            warnings.append(
                "price_near_equilibrium"
            )

        if (
            normalized_trend == "BULLISH"
            and price_zone == "PREMIUM"
        ):
            warnings.append(
                "bullish_market_in_premium"
            )

        if (
            normalized_trend == "BEARISH"
            and price_zone == "DISCOUNT"
        ):
            warnings.append(
                "bearish_market_in_discount"
            )

        if directional_conflict:
            context = "NEUTRAL"

        elif (
            context_score
            >= self.decision_threshold
        ):
            context = "BUY"

        elif (
            context_score
            <= -self.decision_threshold
        ):
            context = "SELL"

        else:
            context = "NEUTRAL"

        context_strength = round(
            min(
                1.0,
                abs(
                    context_score
                ),
            ),
            4,
        )

        return {
            "status": "READY",
            "context": context,
            "context_strength": (
                context_strength
            ),
            "context_score": round(
                context_score,
                4,
            ),
            "current_price": (
                normalized_price
            ),
            "range_high": (
                external_high
            ),
            "range_low": external_low,
            "range_size": (
                external_range[
                    "range_size"
                ]
            ),
            "equilibrium": (
                external_range[
                    "equilibrium"
                ]
            ),
            "position_percent": (
                external_range[
                    "position_percent"
                ]
            ),
            "price_zone": price_zone,
            "near_range_high": (
                near_range_high
            ),
            "near_range_low": (
                near_range_low
            ),
            "external_range": (
                external_range
            ),
            "internal_range": (
                internal_range
            ),
            "trend_direction": (
                normalized_trend
            ),
            "multi_timeframe_direction": (
                normalized_multi
            ),
            "trend_alignment": (
                trend_alignment
            ),
            "directional_conflict": (
                directional_conflict
            ),
            "smart_money_bias": (
                smart_money_bias
            ),
            "blocking_reasons": (
                blocking_reasons
            ),
            "warnings": warnings,
            "candle_count": len(
                normalized_candles
            ),
        }

    def _calculate_context_score(
        self,
        *,
        trend_direction: str,
        multi_timeframe_direction: str,
        price_zone: str,
        near_range_low: bool,
        near_range_high: bool,
        smart_money_bias: str,
    ) -> float:
        score = 0.0

        if trend_direction == "BULLISH":
            score += 0.20

        elif trend_direction == "BEARISH":
            score -= 0.20

        if (
            multi_timeframe_direction
            == "BULLISH"
        ):
            score += 0.30

        elif (
            multi_timeframe_direction
            == "BEARISH"
        ):
            score -= 0.30

        if price_zone == "DISCOUNT":
            score += 0.20

        elif price_zone == "PREMIUM":
            score -= 0.20

        if near_range_low:
            score += 0.10

        if near_range_high:
            score -= 0.10

        if smart_money_bias == "BUY":
            score += 0.20

        elif smart_money_bias == "SELL":
            score -= 0.20

        return max(
            -1.0,
            min(
                score,
                1.0,
            ),
        )

    def _extract_smart_money_bias(
        self,
        result: dict[str, object],
    ) -> str:
        bullish_score = 0
        bearish_score = 0

        structure = result.get(
            "structure",
            {},
        )

        if isinstance(
            structure,
            dict,
        ):
            direction = str(
                structure.get(
                    "direction",
                    "",
                )
            ).strip().upper()

            if direction == "BULLISH":
                bullish_score += 2

            elif direction == "BEARISH":
                bearish_score += 2

            sweep_side = str(
                structure.get(
                    "sweep_side",
                    "",
                )
            ).strip().upper()

            if sweep_side == "SELL_SIDE":
                bullish_score += 1

            elif sweep_side == "BUY_SIDE":
                bearish_score += 1

        for key in (
            "fvg",
            "order_block",
        ):
            component = result.get(
                key,
                {},
            )

            if not isinstance(
                component,
                dict,
            ):
                continue

            direction = str(
                component.get(
                    "direction",
                    "",
                )
            ).strip().upper()

            active = bool(
                component.get(
                    key,
                    False,
                )
            )

            if not active:
                continue

            if direction == "BULLISH":
                bullish_score += 1

            elif direction == "BEARISH":
                bearish_score += 1

        if bullish_score > bearish_score:
            return "BUY"

        if bearish_score > bullish_score:
            return "SELL"

        return "NEUTRAL"

    def _build_range(
        self,
        *,
        range_high: float,
        range_low: float,
        current_price: float,
        allow_outside: bool = False,
    ) -> dict[str, object]:
        range_size = (
            range_high
            - range_low
        )

        if range_size <= 0:
            raise ValueError(
                "El rango debe ser mayor "
                "que cero."
            )

        raw_position = (
            current_price
            - range_low
        ) / range_size

        if (
            not allow_outside
            and not (
                0.0
                <= raw_position
                <= 1.0
            )
        ):
            raise ValueError(
                "El precio debe estar dentro "
                "del rango."
            )

        position_ratio = max(
            0.0,
            min(
                raw_position,
                1.0,
            ),
        )

        equilibrium = (
            range_low
            + range_size / 2.0
        )

        return {
            "high": range_high,
            "low": range_low,
            "range_size": round(
                range_size,
                10,
            ),
            "equilibrium": round(
                equilibrium,
                10,
            ),
            "position_ratio": round(
                position_ratio,
                4,
            ),
            "position_percent": round(
                position_ratio
                * 100.0,
                2,
            ),
            "price_inside_range": (
                range_low
                <= current_price
                <= range_high
            ),
        }

    def _normalize_candle(
        self,
        candle: Any,
    ) -> dict[str, float]:
        values = {
            "open": self._positive_float(
                "candle.open",
                getattr(
                    candle,
                    "open",
                    None,
                ),
            ),
            "high": self._positive_float(
                "candle.high",
                getattr(
                    candle,
                    "high",
                    None,
                ),
            ),
            "low": self._positive_float(
                "candle.low",
                getattr(
                    candle,
                    "low",
                    None,
                ),
            ),
            "close": self._positive_float(
                "candle.close",
                getattr(
                    candle,
                    "close",
                    None,
                ),
            ),
        }

        if (
            values["high"]
            <= values["low"]
        ):
            raise ValueError(
                "candle.high debe ser mayor "
                "que candle.low."
            )

        if not (
            values["low"]
            <= values["open"]
            <= values["high"]
        ):
            raise ValueError(
                "candle.open debe estar dentro "
                "del rango de la vela."
            )

        if not (
            values["low"]
            <= values["close"]
            <= values["high"]
        ):
            raise ValueError(
                "candle.close debe estar dentro "
                "del rango de la vela."
            )

        return values

    def _normalize_direction(
        self,
        value: object,
    ) -> str:
        direction = str(
            value
            or ""
        ).strip().upper()

        aliases = {
            "ALCISTA": "BULLISH",
            "BUY": "BULLISH",
            "LONG": "BULLISH",
            "BAJISTA": "BEARISH",
            "SELL": "BEARISH",
            "SHORT": "BEARISH",
            "SIDEWAYS": "NEUTRAL",
            "RANGE": "NEUTRAL",
            "CONFLICT": "NEUTRAL",
            "INSUFFICIENT_DATA": (
                "NEUTRAL"
            ),
        }

        direction = aliases.get(
            direction,
            direction,
        )

        if (
            direction
            not in self.VALID_DIRECTIONS
        ):
            return "NEUTRAL"

        return direction

    def _positive_float(
        self,
        name: str,
        value: object,
    ) -> float:
        try:
            number = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise TypeError(
                f"{name} debe ser numérico."
            ) from error

        if (
            not isfinite(number)
            or number <= 0
        ):
            raise ValueError(
                f"{name} debe ser mayor "
                "que cero."
            )

        return number

    def _validate_ratio(
        self,
        *,
        name: str,
        value: object,
        allow_zero: bool,
    ) -> float:
        number = float(
            value
        )

        if not isfinite(
            number
        ):
            raise ValueError(
                f"{name} debe ser finito."
            )

        if allow_zero:
            valid = (
                0.0
                <= number
                <= 1.0
            )
        else:
            valid = (
                0.0
                < number
                <= 1.0
            )

        if not valid:
            raise ValueError(
                f"{name} debe estar entre "
                "0 y 1."
            )

        return number
