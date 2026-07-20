from __future__ import annotations

from math import sqrt

import numpy as np


TRADING_DAYS_PER_YEAR = 252


class BenchmarkAnalytics:
    """
    Compara un portafolio contra un benchmark.
    """

    def calculate(
        self,
        *,
        portfolio_returns: list[float],
        benchmark_returns: list[float],
        risk_free_rate: float = 0.0,
    ) -> dict[str, object]:
        if (
            not portfolio_returns
            or not benchmark_returns
        ):
            raise ValueError(
                "returns no puede estar vacío."
            )

        if (
            len(portfolio_returns)
            != len(benchmark_returns)
        ):
            raise ValueError(
                "Las series deben tener "
                "la misma longitud."
            )

        portfolio = np.asarray(
            portfolio_returns,
            dtype=float,
        )

        benchmark = np.asarray(
            benchmark_returns,
            dtype=float,
        )

        if (
            not np.isfinite(portfolio).all()
            or not np.isfinite(benchmark).all()
        ):
            raise ValueError(
                "returns contiene valores inválidos."
            )

        if len(portfolio) < 2:
            raise ValueError(
                "Se requieren al menos "
                "dos observaciones."
            )

        benchmark_variance = float(
            benchmark.var(
                ddof=1
            )
        )

        covariance = float(
            np.cov(
                portfolio,
                benchmark,
                ddof=1,
            )[0, 1]
        )

        beta = (
            covariance
            / benchmark_variance
            if benchmark_variance > 0.0
            else 0.0
        )

        portfolio_annual_return = (
            float(
                portfolio.mean()
            )
            * TRADING_DAYS_PER_YEAR
        )

        benchmark_annual_return = (
            float(
                benchmark.mean()
            )
            * TRADING_DAYS_PER_YEAR
        )

        alpha = (
            portfolio_annual_return
            - (
                risk_free_rate
                + beta
                * (
                    benchmark_annual_return
                    - risk_free_rate
                )
            )
        )

        active_returns = (
            portfolio
            - benchmark
        )

        tracking_error = (
            float(
                active_returns.std(
                    ddof=1
                )
            )
            * sqrt(
                TRADING_DAYS_PER_YEAR
            )
        )

        annualized_active_return = (
            float(
                active_returns.mean()
            )
            * TRADING_DAYS_PER_YEAR
        )

        information_ratio = (
            annualized_active_return
            / tracking_error
            if tracking_error > 0.0
            else 0.0
        )

        portfolio_curve = np.concatenate(
            (
                np.array([1.0]),
                np.cumprod(
                    1.0 + portfolio
                ),
            )
        )

        benchmark_curve = np.concatenate(
            (
                np.array([1.0]),
                np.cumprod(
                    1.0 + benchmark
                ),
            )
        )

        return {
            "beta": float(beta),
            "alpha": float(alpha),
            "tracking_error": float(
                tracking_error
            ),
            "information_ratio": float(
                information_ratio
            ),
            "portfolio_curve": [
                float(value)
                for value in portfolio_curve
            ],
            "benchmark_curve": [
                float(value)
                for value in benchmark_curve
            ],
        }
