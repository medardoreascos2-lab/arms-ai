from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MonteCarloSimulationResultV2:
    """
    Resultado consolidado de múltiples simulaciones
    Monte Carlo sobre una secuencia de PnL.
    """

    starting_balance: float
    final_equities: list[float] = field(
        default_factory=list
    )
    maximum_drawdowns: list[float] = field(
        default_factory=list
    )
    equity_curves: list[list[float]] = field(
        default_factory=list
    )

    def __post_init__(self) -> None:

        self.starting_balance = float(
            self.starting_balance
        )

        if self.starting_balance <= 0.0:
            raise ValueError(
                "starting_balance debe ser mayor que cero."
            )

        self.final_equities = [
            float(value)
            for value in self.final_equities
        ]

        self.maximum_drawdowns = [
            float(value)
            for value in self.maximum_drawdowns
        ]

        self.equity_curves = [
            [
                float(value)
                for value in curve
            ]
            for curve in self.equity_curves
        ]

        if not (
            len(self.final_equities)
            == len(self.maximum_drawdowns)
            == len(self.equity_curves)
        ):
            raise ValueError(
                "Los resultados de simulación "
                "deben tener la misma longitud."
            )

    @property
    def total_simulations(
        self,
    ) -> int:

        return len(
            self.equity_curves
        )

    def summary(
        self,
    ) -> dict[str, float | int]:

        if not self.total_simulations:
            return {
                "total_simulations": 0,
                "starting_balance": (
                    self.starting_balance
                ),
                "average_final_equity": (
                    self.starting_balance
                ),
                "worst_maximum_drawdown": 0.0,
                "average_maximum_drawdown": 0.0,
            }

        return {
            "total_simulations": (
                self.total_simulations
            ),
            "starting_balance": (
                self.starting_balance
            ),
            "average_final_equity": (
                sum(
                    self.final_equities
                )
                / self.total_simulations
            ),
            "worst_maximum_drawdown": max(
                self.maximum_drawdowns
            ),
            "average_maximum_drawdown": (
                sum(
                    self.maximum_drawdowns
                )
                / self.total_simulations
            ),
        }

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "summary": deepcopy(
                self.summary()
            ),
            "starting_balance": (
                self.starting_balance
            ),
            "total_simulations": (
                self.total_simulations
            ),
            "final_equities": deepcopy(
                self.final_equities
            ),
            "maximum_drawdowns": deepcopy(
                self.maximum_drawdowns
            ),
            "equity_curves": deepcopy(
                self.equity_curves
            ),
        }


class MonteCarloSimulatorV2:
    """
    Ejecuta simulaciones Monte Carlo aleatorizando
    el orden histórico de los resultados de trading.
    """

    def __init__(
        self,
        *,
        simulations: int,
        random_seed: int | None = None,
    ) -> None:

        if not isinstance(
            simulations,
            int,
        ):
            raise TypeError(
                "simulations debe ser int."
            )

        if simulations <= 0:
            raise ValueError(
                "simulations debe ser mayor que cero."
            )

        if (
            random_seed is not None
            and not isinstance(
                random_seed,
                int,
            )
        ):
            raise TypeError(
                "random_seed debe ser int o None."
            )

        self.simulations = simulations
        self.random_seed = random_seed

    def simulate(
        self,
        *,
        trade_pnls,
        starting_balance,
    ) -> MonteCarloSimulationResultV2:

        normalized_trade_pnls = (
            self._normalize_trade_pnls(
                trade_pnls
            )
        )

        normalized_starting_balance = (
            self._normalize_starting_balance(
                starting_balance
            )
        )

        random_generator = random.Random(
            self.random_seed
        )

        final_equities: list[float] = []
        maximum_drawdowns: list[float] = []
        equity_curves: list[list[float]] = []

        for _ in range(
            self.simulations
        ):
            shuffled_pnls = list(
                normalized_trade_pnls
            )

            random_generator.shuffle(
                shuffled_pnls
            )

            equity = (
                normalized_starting_balance
            )

            peak_equity = equity
            maximum_drawdown = 0.0

            equity_curve = [
                equity
            ]

            for pnl in shuffled_pnls:
                equity += pnl

                equity_curve.append(
                    equity
                )

                peak_equity = max(
                    peak_equity,
                    equity,
                )

                current_drawdown = (
                    peak_equity
                    - equity
                )

                maximum_drawdown = max(
                    maximum_drawdown,
                    current_drawdown,
                )

            final_equities.append(
                equity
            )

            maximum_drawdowns.append(
                maximum_drawdown
            )

            equity_curves.append(
                equity_curve
            )

        return MonteCarloSimulationResultV2(
            starting_balance=(
                normalized_starting_balance
            ),
            final_equities=final_equities,
            maximum_drawdowns=(
                maximum_drawdowns
            ),
            equity_curves=equity_curves,
        )

    @staticmethod
    def _normalize_trade_pnls(
        trade_pnls,
    ) -> list[float]:

        if isinstance(
            trade_pnls,
            (
                str,
                bytes,
                dict,
            ),
        ) or trade_pnls is None:
            raise TypeError(
                "trade_pnls debe ser una colección."
            )

        try:
            normalized = list(
                trade_pnls
            )
        except TypeError as exc:
            raise TypeError(
                "trade_pnls debe ser una colección."
            ) from exc

        if not normalized:
            raise ValueError(
                "trade_pnls no puede estar vacío."
            )

        values: list[float] = []

        for value in normalized:
            try:
                values.append(
                    float(
                        value
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "Cada trade_pnl debe ser numérico."
                ) from exc

        return values

    @staticmethod
    def _normalize_starting_balance(
        starting_balance,
    ) -> float:

        try:
            normalized = float(
                starting_balance
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "starting_balance debe ser numérico."
            ) from exc

        if normalized <= 0.0:
            raise ValueError(
                "starting_balance debe ser mayor que cero."
            )

        return normalized
