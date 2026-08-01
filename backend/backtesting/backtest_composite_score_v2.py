from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BacktestCompositeScoreResultV2:
    """
    Resultado del análisis compuesto de una estrategia.
    """

    score: float
    grade: str
    strengths: list[str] = field(
        default_factory=list
    )
    weaknesses: list[str] = field(
        default_factory=list
    )
    components: dict[str, float] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:

        normalized_score = float(
            self.score
        )

        self.score = max(
            0.0,
            min(
                100.0,
                normalized_score,
            ),
        )

        self.grade = str(
            self.grade
        ).strip().upper()

        self.strengths = list(
            self.strengths
        )

        self.weaknesses = list(
            self.weaknesses
        )

        self.components = {
            str(key): float(value)
            for key, value
            in self.components.items()
        }

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve una copia segura del resultado.
        """

        return {
            "score": self.score,
            "grade": self.grade,
            "strengths": deepcopy(
                self.strengths
            ),
            "weaknesses": deepcopy(
                self.weaknesses
            ),
            "components": deepcopy(
                self.components
            ),
        }


class BacktestCompositeScoreV2:
    """
    Calcula un score equilibrado de rentabilidad,
    consistencia, riesgo y tamaño de muestra.
    """

    def __init__(
        self,
        *,
        minimum_trades: int = 10,
    ) -> None:

        if not isinstance(
            minimum_trades,
            int,
        ):
            raise TypeError(
                "minimum_trades debe ser int."
            )

        if minimum_trades <= 0:
            raise ValueError(
                "minimum_trades debe ser mayor que cero."
            )

        self.minimum_trades = (
            minimum_trades
        )

    @staticmethod
    def _clamp(
        value: float,
        minimum: float = 0.0,
        maximum: float = 1.0,
    ) -> float:

        return max(
            minimum,
            min(
                maximum,
                float(value),
            ),
        )

    @staticmethod
    def _number(
        metrics: dict[str, Any],
        key: str,
        default: float = 0.0,
    ) -> float:

        value = metrics.get(
            key,
            default,
        )

        if value is None:
            return float(
                default
            )

        try:
            return float(
                value
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                f"{key} debe ser numérico."
            ) from exc

    def calculate(
        self,
        *,
        metrics: dict[str, Any],
    ) -> BacktestCompositeScoreResultV2:

        if not isinstance(
            metrics,
            dict,
        ):
            raise TypeError(
                "metrics debe ser un dict."
            )

        net_pnl = self._number(
            metrics,
            "net_pnl",
        )

        win_rate = self._number(
            metrics,
            "win_rate",
        )

        profit_factor = self._number(
            metrics,
            "profit_factor",
        )

        expectancy = self._number(
            metrics,
            "expectancy",
        )

        maximum_drawdown = abs(
            self._number(
                metrics,
                "maximum_drawdown",
            )
        )

        total_trades = int(
            self._number(
                metrics,
                "total_trades",
            )
        )

        net_pnl_score = (
            25.0
            * self._clamp(
                net_pnl / 1000.0
            )
        )

        win_rate_score = (
            20.0
            * self._clamp(
                win_rate / 0.70
            )
        )

        profit_factor_score = (
            20.0
            * self._clamp(
                (
                    profit_factor
                    - 0.50
                )
                / 2.0
            )
        )

        expectancy_score = (
            15.0
            * self._clamp(
                (
                    expectancy
                    + 20.0
                )
                / 120.0
            )
        )

        drawdown_score = (
            20.0
            * self._clamp(
                1.0
                - (
                    maximum_drawdown
                    / 1500.0
                )
            )
        )

        components = {
            "net_pnl": net_pnl_score,
            "win_rate": win_rate_score,
            "profit_factor": (
                profit_factor_score
            ),
            "expectancy": (
                expectancy_score
            ),
            "maximum_drawdown": (
                drawdown_score
            ),
        }

        raw_score = sum(
            components.values()
        )

        strengths: list[str] = []
        weaknesses: list[str] = []

        if profit_factor >= 2.0:
            strengths.append(
                "HIGH_PROFIT_FACTOR"
            )

        if win_rate >= 0.65:
            strengths.append(
                "HIGH_WIN_RATE"
            )

        if (
            maximum_drawdown <= 250.0
            and net_pnl > 0
        ):
            strengths.append(
                "LOW_DRAWDOWN"
            )

        if expectancy >= 50.0:
            strengths.append(
                "HIGH_EXPECTANCY"
            )

        if net_pnl < 0:
            weaknesses.append(
                "NEGATIVE_NET_PNL"
            )

        if profit_factor < 1.0:
            weaknesses.append(
                "LOW_PROFIT_FACTOR"
            )

        if expectancy < 0:
            weaknesses.append(
                "NEGATIVE_EXPECTANCY"
            )

        if maximum_drawdown >= 1000.0:
            weaknesses.append(
                "HIGH_DRAWDOWN"
            )

        score = raw_score

        if total_trades < self.minimum_trades:
            weaknesses.append(
                "INSUFFICIENT_TRADES"
            )

            sample_ratio = self._clamp(
                total_trades
                / self.minimum_trades
            )

            sample_multiplier = (
                0.45
                + (
                    0.20
                    * sample_ratio
                )
            )

            score *= sample_multiplier

        score = round(
            self._clamp(
                score,
                minimum=0.0,
                maximum=100.0,
            ),
            2,
        )

        grade = self._grade_for_score(
            score
        )

        return BacktestCompositeScoreResultV2(
            score=score,
            grade=grade,
            strengths=strengths,
            weaknesses=weaknesses,
            components=components,
        )

    @staticmethod
    def _grade_for_score(
        score: float,
    ) -> str:

        if score >= 90.0:
            return "A+"

        if score >= 80.0:
            return "A"

        if score >= 70.0:
            return "B"

        if score >= 60.0:
            return "C"

        if score >= 40.0:
            return "D"

        return "F"
