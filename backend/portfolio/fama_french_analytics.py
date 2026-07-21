from __future__ import annotations

import numpy as np


TRADING_DAYS_PER_YEAR = 252


class FamaFrenchAnalytics:
    """
    Modelo Fama-French de tres factores.
    """

    def calculate(
        self,
        *,
        portfolio_returns: list[float],
        market_returns: list[float],
        smb_returns: list[float],
        hml_returns: list[float],
        risk_free_rate: float = 0.0,
    ) -> dict[str, float]:
        series = [
            portfolio_returns,
            market_returns,
            smb_returns,
            hml_returns,
        ]

        length = len(portfolio_returns)

        if any(len(s) != length for s in series):
            raise ValueError(
                "Las series deben tener la misma longitud."
            )

        if length == 0:
            raise ValueError(
                "returns no puede estar vacío."
            )

        y = np.asarray(
            portfolio_returns,
            dtype=float,
        )

        market = np.asarray(
            market_returns,
            dtype=float,
        )

        smb = np.asarray(
            smb_returns,
            dtype=float,
        )

        hml = np.asarray(
            hml_returns,
            dtype=float,
        )

        if not (
            np.isfinite(y).all()
            and np.isfinite(market).all()
            and np.isfinite(smb).all()
            and np.isfinite(hml).all()
        ):
            raise ValueError(
                "returns contiene valores inválidos."
            )

        X = np.column_stack(
            (
                np.ones(length),
                market,
                smb,
                hml,
            )
        )

        coefficients, *_ = np.linalg.lstsq(
            X,
            y,
            rcond=None,
        )

        alpha = float(
            coefficients[0]
            * TRADING_DAYS_PER_YEAR
        )

        beta_market = float(coefficients[1])
        beta_smb = float(coefficients[2])
        beta_hml = float(coefficients[3])

        fitted = X @ coefficients

        ss_res = float(
            np.sum((y - fitted) ** 2)
        )

        ss_tot = float(
            np.sum((y - y.mean()) ** 2)
        )

        r_squared = (
            1.0 - ss_res / ss_tot
            if ss_tot > 0
            else 1.0
        )

        market_premium = (
            float(market.mean())
            * TRADING_DAYS_PER_YEAR
            - risk_free_rate
        )

        smb_premium = (
            float(smb.mean())
            * TRADING_DAYS_PER_YEAR
        )

        hml_premium = (
            float(hml.mean())
            * TRADING_DAYS_PER_YEAR
        )

        expected_return = (
            risk_free_rate
            + beta_market * market_premium
            + beta_smb * smb_premium
            + beta_hml * hml_premium
        )

        return {
            "alpha": alpha,
            "beta_market": beta_market,
            "beta_smb": beta_smb,
            "beta_hml": beta_hml,
            "r_squared": float(r_squared),
            "expected_return": float(expected_return),
        }
