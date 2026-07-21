from __future__ import annotations

from math import sqrt

import numpy as np


TRADING_DAYS_PER_YEAR = 252


class CapmAnalytics:
    """
    Calcula métricas CAPM para un portafolio
    frente a un índice de mercado.
    """

    def calculate(
        self,
        *,
        portfolio_returns: list[float],
        market_returns: list[float],
        risk_free_rate: float = 0.0,
    ) -> dict[str, float]:
        if (
            not portfolio_returns
            or not market_returns
        ):
            raise ValueError(
                "returns no puede estar vacío."
            )

        if (
            len(portfolio_returns)
            != len(market_returns)
        ):
            raise ValueError(
                "Las series deben tener "
                "la misma longitud."
            )

        portfolio = np.asarray(
            portfolio_returns,
            dtype=float,
        )

        market = np.asarray(
            market_returns,
            dtype=float,
        )

        if (
            not np.isfinite(portfolio).all()
            or not np.isfinite(market).all()
        ):
            raise ValueError(
                "returns contiene valores inválidos."
            )

        if len(portfolio) < 2:
            raise ValueError(
                "Se requieren al menos "
                "dos observaciones."
            )

        market_variance = float(
            market.var(
                ddof=1
            )
        )

        covariance = float(
            np.cov(
                portfolio,
                market,
                ddof=1,
            )[0, 1]
        )

        beta = (
            covariance
            / market_variance
            if market_variance > 0.0
            else 0.0
        )

        portfolio_annual_return = (
            float(
                portfolio.mean()
            )
            * TRADING_DAYS_PER_YEAR
        )

        market_annual_return = (
            float(
                market.mean()
            )
            * TRADING_DAYS_PER_YEAR
        )

        market_risk_premium = (
            market_annual_return
            - risk_free_rate
        )

        capm_expected_return = (
            risk_free_rate
            + beta
            * market_risk_premium
        )

        jensens_alpha = (
            portfolio_annual_return
            - capm_expected_return
        )

        treynor_ratio = (
            (
                portfolio_annual_return
                - risk_free_rate
            )
            / beta
            if abs(beta) > 1e-12
            else 0.0
        )

        portfolio_volatility = (
            float(
                portfolio.std(
                    ddof=1
                )
            )
            * sqrt(
                TRADING_DAYS_PER_YEAR
            )
        )

        market_volatility = (
            float(
                market.std(
                    ddof=1
                )
            )
            * sqrt(
                TRADING_DAYS_PER_YEAR
            )
        )

        portfolio_sharpe = (
            (
                portfolio_annual_return
                - risk_free_rate
            )
            / portfolio_volatility
            if portfolio_volatility > 0.0
            else 0.0
        )

        modigliani_m2 = (
            risk_free_rate
            + portfolio_sharpe
            * market_volatility
        )

        return {
            "beta": float(beta),
            "jensens_alpha": float(
                jensens_alpha
            ),
            "capm_expected_return": float(
                capm_expected_return
            ),
            "market_risk_premium": float(
                market_risk_premium
            ),
            "treynor_ratio": float(
                treynor_ratio
            ),
            "modigliani_m2": float(
                modigliani_m2
            ),
        }
