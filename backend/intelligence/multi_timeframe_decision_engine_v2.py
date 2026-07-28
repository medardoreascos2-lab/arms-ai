from __future__ import annotations

from math import isfinite
from typing import Any


class MultiTimeframeDecisionEngineV2:
    """
    Consolida tendencias de múltiples temporalidades.

    Pesos predeterminados:

    - 1H  = 35%
    - 15M = 30%
    - 5M  = 25%
    - 1M  = 10%

    Resultados posibles:

    - BULLISH
    - BEARISH
    - NEUTRAL
    - CONFLICT
    - INSUFFICIENT_DATA
    """

    DEFAULT_WEIGHTS: dict[str, float] = {
        "1M": 0.10,
        "5M": 0.25,
        "15M": 0.30,
        "1H": 0.35,
    }

    VALID_DIRECTIONS = {
        "BULLISH",
        "BEARISH",
        "SIDEWAYS",
        "INSUFFICIENT_DATA",
    }

    def __init__(
        self,
        *,
        trend_engine: Any,
        timeframe_weights: dict[str, float]
        | None = None,
        minimum_ready_weight: float = 0.65,
        neutral_threshold: float = 0.15,
        conflict_weight_threshold: float = 0.25,
        dominance_margin: float = 0.35,
    ) -> None:
        if not callable(
            getattr(
                trend_engine,
                "analyze",
                None,
            )
        ):
            raise TypeError(
                "trend_engine debe implementar "
                "analyze()."
            )

        weights = (
            dict(timeframe_weights)
            if timeframe_weights is not None
            else dict(self.DEFAULT_WEIGHTS)
        )

        normalized_weights = (
            self._validate_and_normalize_weights(
                weights
            )
        )

        self.trend_engine = trend_engine
        self.timeframe_weights = (
            normalized_weights
        )

        self.minimum_ready_weight = (
            self._validate_ratio(
                "minimum_ready_weight",
                minimum_ready_weight,
                allow_zero=False,
            )
        )

        self.neutral_threshold = (
            self._validate_ratio(
                "neutral_threshold",
                neutral_threshold,
                allow_zero=True,
            )
        )

        self.conflict_weight_threshold = (
            self._validate_ratio(
                "conflict_weight_threshold",
                conflict_weight_threshold,
                allow_zero=True,
            )
        )

        self.dominance_margin = (
            self._validate_ratio(
                "dominance_margin",
                dominance_margin,
                allow_zero=True,
            )
        )

    def analyze(
        self,
        *,
        symbol: str,
    ) -> dict[str, object]:
        normalized_symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        timeframe_results: dict[
            str,
            dict[str, object],
        ] = {}

        timeframe_votes: dict[
            str,
            str,
        ] = {}

        bullish_weight = 0.0
        bearish_weight = 0.0
        sideways_weight = 0.0
        insufficient_weight = 0.0
        ready_weight = 0.0
        weighted_score = 0.0

        aligned_timeframes: list[str] = []
        conflicting_timeframes: list[str] = []
        insufficient_timeframes: list[str] = []

        for (
            timeframe,
            weight,
        ) in self.timeframe_weights.items():
            trend = self.trend_engine.analyze(
                symbol=normalized_symbol,
                timeframe=timeframe,
            )

            if not isinstance(
                trend,
                dict,
            ):
                raise TypeError(
                    "TrendEngineV2 debe devolver "
                    "un dict."
                )

            direction = str(
                trend.get(
                    "direction",
                    "INSUFFICIENT_DATA",
                )
            ).strip().upper()

            if direction not in (
                self.VALID_DIRECTIONS
            ):
                direction = "SIDEWAYS"

            confidence = self._normalize_confidence(
                trend.get(
                    "confidence",
                    0.0,
                )
            )

            normalized_result = dict(
                trend
            )

            normalized_result[
                "direction"
            ] = direction

            normalized_result[
                "confidence"
            ] = confidence

            normalized_result[
                "weight"
            ] = weight

            timeframe_results[
                timeframe
            ] = normalized_result

            timeframe_votes[
                timeframe
            ] = direction

            if direction == "INSUFFICIENT_DATA":
                insufficient_weight += weight

                insufficient_timeframes.append(
                    timeframe
                )

                continue

            ready_weight += weight

            if direction == "BULLISH":
                bullish_weight += weight

                weighted_score += (
                    weight
                    * confidence
                )

            elif direction == "BEARISH":
                bearish_weight += weight

                weighted_score -= (
                    weight
                    * confidence
                )

            else:
                sideways_weight += weight

        if (
            ready_weight
            < self.minimum_ready_weight
        ):
            return {
                "status": "INSUFFICIENT_DATA",
                "direction": (
                    "INSUFFICIENT_DATA"
                ),
                "symbol": normalized_symbol,
                "confidence": 0.0,
                "weighted_score": 0.0,
                "ready_weight": round(
                    ready_weight,
                    4,
                ),
                "required_ready_weight": (
                    self.minimum_ready_weight
                ),
                "bullish_weight": round(
                    bullish_weight,
                    4,
                ),
                "bearish_weight": round(
                    bearish_weight,
                    4,
                ),
                "sideways_weight": round(
                    sideways_weight,
                    4,
                ),
                "insufficient_weight": round(
                    insufficient_weight,
                    4,
                ),
                "timeframe_votes": (
                    timeframe_votes
                ),
                "timeframe_results": (
                    timeframe_results
                ),
                "aligned_timeframes": [],
                "conflicting_timeframes": [],
                "insufficient_timeframes": (
                    insufficient_timeframes
                ),
                "blocking_reasons": [
                    "insufficient_timeframe_data"
                ],
                "weights": dict(
                    self.timeframe_weights
                ),
            }

        normalized_score = (
            weighted_score
            / ready_weight
        )

        directional_difference = abs(
            bullish_weight
            - bearish_weight
        )

        has_bullish_conflict = (
            bullish_weight
            >= self.conflict_weight_threshold
        )

        has_bearish_conflict = (
            bearish_weight
            >= self.conflict_weight_threshold
        )

        strong_conflict = (
            has_bullish_conflict
            and has_bearish_conflict
            and directional_difference
            < self.dominance_margin
        )

        if strong_conflict:
            direction = "CONFLICT"

        elif (
            abs(normalized_score)
            < self.neutral_threshold
        ):
            direction = "NEUTRAL"

        elif normalized_score > 0:
            direction = "BULLISH"

        else:
            direction = "BEARISH"

        for (
            timeframe,
            vote,
        ) in timeframe_votes.items():
            if vote == "INSUFFICIENT_DATA":
                continue

            if direction == "BULLISH":
                if vote == "BULLISH":
                    aligned_timeframes.append(
                        timeframe
                    )
                elif vote == "BEARISH":
                    conflicting_timeframes.append(
                        timeframe
                    )

            elif direction == "BEARISH":
                if vote == "BEARISH":
                    aligned_timeframes.append(
                        timeframe
                    )
                elif vote == "BULLISH":
                    conflicting_timeframes.append(
                        timeframe
                    )

            elif direction == "CONFLICT":
                if vote in {
                    "BULLISH",
                    "BEARISH",
                }:
                    conflicting_timeframes.append(
                        timeframe
                    )

            elif direction == "NEUTRAL":
                if vote == "SIDEWAYS":
                    aligned_timeframes.append(
                        timeframe
                    )
                elif vote in {
                    "BULLISH",
                    "BEARISH",
                }:
                    conflicting_timeframes.append(
                        timeframe
                    )

        blocking_reasons: list[str] = []

        if direction == "CONFLICT":
            blocking_reasons.append(
                "timeframe_direction_conflict"
            )

        confidence = self._calculate_confidence(
            direction=direction,
            normalized_score=(
                normalized_score
            ),
            bullish_weight=(
                bullish_weight
            ),
            bearish_weight=(
                bearish_weight
            ),
            sideways_weight=(
                sideways_weight
            ),
            ready_weight=ready_weight,
        )

        return {
            "status": "READY",
            "direction": direction,
            "symbol": normalized_symbol,
            "confidence": confidence,
            "weighted_score": round(
                normalized_score,
                4,
            ),
            "ready_weight": round(
                ready_weight,
                4,
            ),
            "required_ready_weight": (
                self.minimum_ready_weight
            ),
            "bullish_weight": round(
                bullish_weight,
                4,
            ),
            "bearish_weight": round(
                bearish_weight,
                4,
            ),
            "sideways_weight": round(
                sideways_weight,
                4,
            ),
            "insufficient_weight": round(
                insufficient_weight,
                4,
            ),
            "timeframe_votes": (
                timeframe_votes
            ),
            "timeframe_results": (
                timeframe_results
            ),
            "aligned_timeframes": (
                aligned_timeframes
            ),
            "conflicting_timeframes": (
                conflicting_timeframes
            ),
            "insufficient_timeframes": (
                insufficient_timeframes
            ),
            "blocking_reasons": (
                blocking_reasons
            ),
            "weights": dict(
                self.timeframe_weights
            ),
        }

    def _calculate_confidence(
        self,
        *,
        direction: str,
        normalized_score: float,
        bullish_weight: float,
        bearish_weight: float,
        sideways_weight: float,
        ready_weight: float,
    ) -> float:
        if ready_weight <= 0:
            return 0.0

        if direction in {
            "BULLISH",
            "BEARISH",
        }:
            confidence = abs(
                normalized_score
            )

        elif direction == "NEUTRAL":
            confidence = (
                sideways_weight
                / ready_weight
            )

        else:
            directional_total = (
                bullish_weight
                + bearish_weight
            )

            if directional_total <= 0:
                confidence = 0.0
            else:
                balance = (
                    1.0
                    - abs(
                        bullish_weight
                        - bearish_weight
                    )
                    / directional_total
                )

                confidence = balance

        return round(
            max(
                0.0,
                min(
                    confidence,
                    1.0,
                ),
            ),
            4,
        )

    def _validate_and_normalize_weights(
        self,
        weights: dict[str, float],
    ) -> dict[str, float]:
        if not isinstance(
            weights,
            dict,
        ):
            raise TypeError(
                "timeframe_weights debe ser "
                "un dict."
            )

        if not weights:
            raise ValueError(
                "timeframe_weights no puede "
                "estar vacío."
            )

        normalized: dict[
            str,
            float,
        ] = {}

        total = 0.0

        for (
            timeframe,
            raw_weight,
        ) in weights.items():
            normalized_timeframe = (
                str(timeframe)
                .strip()
                .upper()
            )

            if not normalized_timeframe:
                raise ValueError(
                    "Los timeframes no pueden "
                    "estar vacíos."
                )

            weight = float(
                raw_weight
            )

            if (
                not isfinite(weight)
                or weight <= 0
            ):
                raise ValueError(
                    "Todos los pesos deben ser "
                    "mayores que cero."
                )

            if (
                normalized_timeframe
                in normalized
            ):
                raise ValueError(
                    "Existen temporalidades "
                    "duplicadas."
                )

            normalized[
                normalized_timeframe
            ] = weight

            total += weight

        if total <= 0:
            raise ValueError(
                "La suma de pesos debe ser "
                "mayor que cero."
            )

        return {
            timeframe: round(
                weight / total,
                10,
            )
            for (
                timeframe,
                weight,
            ) in normalized.items()
        }

    def _normalize_confidence(
        self,
        value: object,
    ) -> float:
        confidence = float(
            value
        )

        if not isfinite(
            confidence
        ):
            raise ValueError(
                "La confianza debe ser finita."
            )

        if (
            confidence > 1.0
            and confidence <= 100.0
        ):
            confidence = (
                confidence
                / 100.0
            )

        if not (
            0.0
            <= confidence
            <= 1.0
        ):
            raise ValueError(
                "La confianza debe estar "
                "entre 0 y 1."
            )

        return round(
            confidence,
            4,
        )

    def _validate_ratio(
        self,
        name: str,
        value: object,
        *,
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

        minimum = (
            0.0
            if allow_zero
            else 0.0
        )

        if allow_zero:
            valid = (
                minimum
                <= number
                <= 1.0
            )
        else:
            valid = (
                minimum
                < number
                <= 1.0
            )

        if not valid:
            raise ValueError(
                f"{name} debe estar entre "
                "0 y 1."
            )

        return number
