from __future__ import annotations

from math import sqrt

import pandas as pd


TRADING_DAYS_PER_YEAR = 252


class PortfolioBacktest:
    """
    Ejecuta un backtest buy-and-hold con pesos fijos.
    """

    def run(
        self,
        *,
        prices: pd.DataFrame,
        weights: dict[str, float],
        initial_value: float = 1000.0,
        risk_free_rate: float = 0.0,
    ) -> dict[str, object]:
        if prices.empty:
            raise ValueError(
                "prices no puede estar vacío."
            )

        if initial_value <= 0.0:
            raise ValueError(
                "initial_value debe ser mayor que cero."
            )

        if not weights:
            raise ValueError(
                "weights no puede estar vacío."
            )

        weight_sum = sum(
            float(value)
            for value in weights.values()
        )

        if abs(weight_sum - 1.0) > 1e-9:
            raise ValueError(
                "weights debe sumar 1.0."
            )

        missing_assets = set(weights) - set(
            prices.columns
        )

        if missing_assets:
            raise ValueError(
                "prices no contiene todos los activos "
                "definidos en weights."
            )

        selected_prices = (
            prices[list(weights)]
            .astype(float)
            .dropna(how="any")
        )

        if len(selected_prices) < 2:
            raise ValueError(
                "El historial debe contener "
                "al menos dos observaciones."
            )

        normalized_prices = (
            selected_prices
            / selected_prices.iloc[0]
        )

        weighted_values = normalized_prices.mul(
            pd.Series(weights),
            axis="columns",
        )

        equity_series = (
            weighted_values.sum(axis=1)
            * initial_value
        )

        daily_returns = (
            equity_series
            .pct_change()
            .dropna()
        )

        final_value = float(
            equity_series.iloc[-1]
        )

        total_return = (
            final_value / initial_value
        ) - 1.0

        periods = len(daily_returns)

        annualized_return = (
            (1.0 + total_return)
            ** (
                TRADING_DAYS_PER_YEAR
                / periods
            )
            - 1.0
            if periods > 0
            and total_return > -1.0
            else 0.0
        )

        annualized_volatility = (
            float(
                daily_returns.std(
                    ddof=1
                )
            )
            * sqrt(
                TRADING_DAYS_PER_YEAR
            )
            if len(daily_returns) > 1
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

        running_maximum = (
            equity_series.cummax()
        )

        drawdowns = (
            equity_series
            / running_maximum
        ) - 1.0

        maximum_drawdown = float(
            drawdowns.min()
        )

        return {
            "initial_value": float(
                initial_value
            ),
            "final_value": final_value,
            "equity_curve": [
                float(value)
                for value in equity_series.tolist()
            ],
            "total_return": float(
                total_return
            ),
            "annualized_return": float(
                annualized_return
            ),
            "annualized_volatility": float(
                annualized_volatility
            ),
            "sharpe_ratio": float(
                sharpe_ratio
            ),
            "maximum_drawdown": (
                maximum_drawdown
            ),
        }
