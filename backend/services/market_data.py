from __future__ import annotations

import pandas as pd
import yfinance as yf


def download_prices(
    symbols: list[str],
    period: str = "1y",
) -> pd.DataFrame:
    """
    Descarga precios históricos desde Yahoo Finance.
    """

    normalized_symbols = [
        symbol.strip().upper()
        for symbol in symbols
        if symbol.strip()
    ]

    if not normalized_symbols:
        raise ValueError(
            "symbols no puede estar vacío."
        )

    data = yf.download(
        normalized_symbols,
        period=period,
        auto_adjust=True,
        progress=False,
    )

    if data.empty:
        raise ValueError(
            "No se encontraron precios."
        )

    if len(normalized_symbols) == 1:
        if "Close" not in data.columns:
            raise ValueError(
                "No se encontraron precios de cierre."
            )

        prices = data["Close"].to_frame(
            normalized_symbols[0]
        )
    else:
        if (
            not isinstance(
                data.columns,
                pd.MultiIndex,
            )
            or "Close"
            not in data.columns.get_level_values(0)
        ):
            raise ValueError(
                "No se encontraron precios de cierre."
            )

        prices = data["Close"]

    prices = prices.dropna(
        how="all"
    )

    if prices.empty:
        raise ValueError(
            "No se encontraron precios válidos."
        )

    return prices
