from __future__ import annotations

from math import sqrt

import numpy as np


TRADING_DAYS_PER_YEAR = 252


class RiskAnalytics:
    """
    Calcula métricas de rendimiento y riesgo
    a partir de una serie de retornos periódicos.
    """

    def calculate(
        self,
        *,
        returns: list[float],
        risk_free_rate: float = 0.0,
    ) -> dict[str, float]:
        if not returns:
            raise ValueError(
                "returns no puede estar vacío."
            )

        values = np.asarray(
            returns,
            dtype=float,
        )

        if not np.isfinite(values).all():
            raise ValueError(
                "returns contiene valores inválidos."
            )

        mean_return = float(
            values.mean()
        )

        annualized_return = (
            mean_return
            * TRADING_DAYS_PER_YEAR
        )

        annualized_volatility = (
            float(
                values.std(
                    ddof=1
                )
            )
            * sqrt(
                TRADING_DAYS_PER_YEAR
            )
            if len(values) > 1
            else 0.0
        )

        sharpe_ratio = (
            (
                annualized_return
                - risk_free_rate
            )
            / annualized_volatility
            if annualized_volatility > 0.0
            else 0.0
        )

        downside_returns = values[
            values < 0.0
        ]

        downside_deviation = (
            float(
                downside_returns.std(
                    ddof=1
                )
            )
            * sqrt(
                TRADING_DAYS_PER_YEAR
            )
            if len(downside_returns) > 1
            else 0.0
        )

        sortino_ratio = (
            (
                annualized_return
                - risk_free_rate
            )
            / downside_deviation
            if downside_deviation > 0.0
            else 0.0
        )

        equity_curve = np.cumprod(
            1.0 + values
        )

        running_maximum = np.maximum.accumulate(
            equity_curve
        )

        drawdowns = (
            equity_curve
            / running_maximum
        ) - 1.0

        maximum_drawdown = float(
            drawdowns.min()
        )

        calmar_ratio = (
            annualized_return
            / abs(
                maximum_drawdown
            )
            if maximum_drawdown < 0.0
            else 0.0
        )

        value_at_risk_95 = float(
            np.percentile(
                values,
                5,
            )
        )

        tail_losses = values[
            values <= value_at_risk_95
        ]

        conditional_value_at_risk_95 = (
            float(
                tail_losses.mean()
            )
            if len(tail_losses) > 0
            else value_at_risk_95
        )

        return {
            "annualized_return": (
                annualized_return
            ),
            "annualized_volatility": (
                annualized_volatility
            ),
            "sharpe_ratio": (
                sharpe_ratio
            ),
            "sortino_ratio": (
                sortino_ratio
            ),
            "maximum_drawdown": (
                maximum_drawdown
            ),
            "calmar_ratio": (
                calmar_ratio
            ),
            "value_at_risk_95": (
                min(
                    value_at_risk_95,
                    0.0,
                )
            ),
            "conditional_value_at_risk_95": (
                min(
                    conditional_value_at_risk_95,
                    value_at_risk_95,
                    0.0,
                )
            ),
        }
