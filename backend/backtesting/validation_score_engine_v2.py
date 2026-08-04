from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ValidationScoreResultV2:
    """
    Resultado del cálculo ponderado de validación.
    """

    score: float
    components: dict[str, float]
    normalized_scores: dict[str, float]
    weights: dict[str, float]

    def __post_init__(self) -> None:

        self.score = round(
            float(self.score),
            2,
        )

        self.components = {
            str(key): float(value)
            for key, value in (
                self.components.items()
            )
        }

        self.normalized_scores = {
            str(key): float(value)
            for key, value in (
                self.normalized_scores.items()
            )
        }

        self.weights = {
            str(key): float(value)
            for key, value in (
                self.weights.items()
            )
        }

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "score": self.score,
            "components": deepcopy(
                self.components
            ),
            "normalized_scores": deepcopy(
                self.normalized_scores
            ),
            "weights": deepcopy(
                self.weights
            ),
        }


class ValidationScoreEngineV2:
    """
    Calcula un score global de validación
    usando Backtest, Walk Forward y Monte Carlo.
    """

    def __init__(
        self,
        *,
        backtest_weight: float = 1 / 3,
        walk_forward_weight: float = 1 / 3,
        monte_carlo_weight: float = 1 / 3,
    ) -> None:

        weights = {
            "backtest_weight": backtest_weight,
            "walk_forward_weight": (
                walk_forward_weight
            ),
            "monte_carlo_weight": (
                monte_carlo_weight
            ),
        }

        normalized_weights: dict[
            str,
            float
        ] = {}

        for name, value in weights.items():

            if (
                not isinstance(
                    value,
                    (
                        int,
                        float,
                    ),
                )
                or isinstance(
                    value,
                    bool,
                )
            ):
                raise TypeError(
                    f"{name} debe ser numérico."
                )

            normalized_value = float(
                value
            )

            if normalized_value < 0.0:
                raise ValueError(
                    f"{name} no puede ser negativo."
                )

            normalized_weights[
                name
            ] = normalized_value

        weight_sum = sum(
            normalized_weights.values()
        )

        if abs(
            weight_sum - 1.0
        ) > 1e-9:
            raise ValueError(
                "Los weights deben sumar 1.0."
            )

        self.backtest_weight = (
            normalized_weights[
                "backtest_weight"
            ]
        )

        self.walk_forward_weight = (
            normalized_weights[
                "walk_forward_weight"
            ]
        )

        self.monte_carlo_weight = (
            normalized_weights[
                "monte_carlo_weight"
            ]
        )

    def calculate(
        self,
        *,
        backtest_score,
        walk_forward_score,
        monte_carlo_score,
    ) -> ValidationScoreResultV2:

        normalized_scores = {
            "backtest": (
                self._normalize_score(
                    backtest_score
                )
            ),
            "walk_forward": (
                self._normalize_score(
                    walk_forward_score
                )
            ),
            "monte_carlo": (
                self._normalize_score(
                    monte_carlo_score
                )
            ),
        }

        weights = {
            "backtest": (
                self.backtest_weight
            ),
            "walk_forward": (
                self.walk_forward_weight
            ),
            "monte_carlo": (
                self.monte_carlo_weight
            ),
        }

        components = {
            name: (
                normalized_scores[name]
                * weights[name]
            )
            for name in normalized_scores
        }

        score = round(
            sum(
                components.values()
            ),
            2,
        )

        return ValidationScoreResultV2(
            score=score,
            components=components,
            normalized_scores=(
                normalized_scores
            ),
            weights=weights,
        )

    @staticmethod
    def _normalize_score(
        value,
    ) -> float:

        if (
            not isinstance(
                value,
                (
                    int,
                    float,
                ),
            )
            or isinstance(
                value,
                bool,
            )
        ):
            raise TypeError(
                "score debe ser numérico."
            )

        normalized = float(
            value
        )

        return min(
            100.0,
            max(
                0.0,
                normalized,
            ),
        )
