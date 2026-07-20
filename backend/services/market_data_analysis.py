from __future__ import annotations

from math import sqrt

import pandas as pd


TRADING_DAYS_PER_YEAR = 252


def build_portfolio_inputs_from_prices(
    prices: pd.DataFrame,
) -> dict[str, dict[str, object]]:
    """
    Convierte precios históricos en entradas
    compatibles con el motor de portafolio.
    """

    if prices.empty:
        raise ValueError(
            "prices no puede estar vacío."
        )

    cleaned_prices = prices.dropna(
        how="all"
    )

    if len(cleaned_prices) < 2:
        raise ValueError(
            "El historial debe contener "
            "al menos dos observaciones."
        )

    returns_frame = (
        cleaned_prices
        .pct_change()
        .dropna(
            how="all"
        )
    )

    if returns_frame.empty:
        raise ValueError(
            "El historial no permite "
            "calcular rendimientos."
        )

    returns: dict[str, list[float]] = {}
    volatilities: dict[str, float] = {}
    expected_returns: dict[str, float] = {}

    for column in returns_frame.columns:
        symbol = str(
            column
        ).strip().upper()

        series = (
            returns_frame[column]
            .dropna()
            .astype(float)
        )

        if series.empty:
            raise ValueError(
                f"El historial de {symbol} "
                "no permite calcular rendimientos."
            )

        returns[symbol] = [
            round(
                float(value),
                10,
            )
            for value in series.tolist()
        ]

        expected_return = (
            float(
                series.mean()
            )
            * TRADING_DAYS_PER_YEAR
        )

        volatility = (
            float(
                series.std(
                    ddof=1
                )
            )
            * sqrt(
                TRADING_DAYS_PER_YEAR
            )
            if len(series) > 1
            else 0.0
        )

        expected_returns[symbol] = round(
            expected_return,
            10,
        )

        volatilities[symbol] = round(
            max(
                volatility,
                0.0,
            ),
            10,
        )

    return {
        "returns": returns,
        "volatilities": volatilities,
        "expected_returns": expected_returns,
    }
