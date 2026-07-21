from __future__ import annotations

from math import sqrt

import numpy as np


TRADING_DAYS_PER_YEAR = 252


class RollingAnalytics:
    """
    Calcula métricas móviles sobre una serie
    de retornos.
    """

    def calculate(
        self,
        *,
        returns: list[float],
        window: int,
        risk_free_rate: float = 0.0,
    ) -> dict[str, list[float]]:
        if not returns:
            raise ValueError(
                "returns no puede estar vacío."
            )

        values = np.asarray(
            returns,
            dtype=float,
        )

        if window <= 0 or window > len(values):
            raise ValueError(
                "window inválido."
            )

        rolling_volatility: list[float] = []
        rolling_sharpe: list[float] = []
        rolling_drawdown: list[float] = []

        for start in range(
            len(values) - window + 1
        ):
            sample = values[
                start : start + window
            ]

            mean_return = float(
                sample.mean()
            )

            volatility = (
                float(
                    sample.std(ddof=1)
                )
                * sqrt(
                    TRADING_DAYS_PER_YEAR
                )
                if len(sample) > 1
                else 0.0
            )

            annual_return = (
                mean_return
                * TRADING_DAYS_PER_YEAR
            )

            sharpe = (
                (
                    annual_return
                    - risk_free_rate
                )
                / volatility
                if volatility > 0.0
                else 0.0
            )

            equity = np.cumprod(
                1.0 + sample
            )

            running_max = (
                np.maximum.accumulate(
                    equity
                )
            )

            drawdown = float(
                (
                    equity
                    / running_max
                    - 1.0
                ).min()
            )

            rolling_volatility.append(
                volatility
            )
            rolling_sharpe.append(
                sharpe
            )
            rolling_drawdown.append(
                drawdown
            )

        return {
            "rolling_volatility":
                rolling_volatility,
            "rolling_sharpe":
                rolling_sharpe,
            "rolling_drawdown":
                rolling_drawdown,
        }
