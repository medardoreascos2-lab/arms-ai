from __future__ import annotations

from copy import deepcopy
from typing import Any


class InstrumentProfileEngine:
    """
    Proporciona perfiles normalizados
    de instrumentos de futuros.
    """

    def __init__(self) -> None:
        self._profiles: dict[
            str,
            dict[str, Any],
        ] = {
            "MNQ": {
                "symbol": "MNQ",
                "name": (
                    "Micro E-mini Nasdaq-100"
                ),
                "point_value": 2.0,
                "tick_size": 0.25,
                "tick_value": 0.50,
                "maximum_contracts": 20,
            },
            "NQ": {
                "symbol": "NQ",
                "name": (
                    "E-mini Nasdaq-100"
                ),
                "point_value": 20.0,
                "tick_size": 0.25,
                "tick_value": 5.0,
                "maximum_contracts": 5,
            },
            "MES": {
                "symbol": "MES",
                "name": (
                    "Micro E-mini S&P 500"
                ),
                "point_value": 5.0,
                "tick_size": 0.25,
                "tick_value": 1.25,
                "maximum_contracts": 20,
            },
            "ES": {
                "symbol": "ES",
                "name": (
                    "E-mini S&P 500"
                ),
                "point_value": 50.0,
                "tick_size": 0.25,
                "tick_value": 12.50,
                "maximum_contracts": 5,
            },
        }

    def get_profile(
        self,
        *,
        symbol: str,
    ) -> dict[str, Any]:
        normalized_symbol = str(
            symbol
        ).strip().upper()

        if not normalized_symbol:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        profile = self._profiles.get(
            normalized_symbol
        )

        if profile is None:
            raise ValueError(
                f"El símbolo {normalized_symbol} "
                "no está soportado."
            )

        return deepcopy(
            profile
        )

    def is_supported(
        self,
        *,
        symbol: str,
    ) -> bool:
        normalized_symbol = str(
            symbol
        ).strip().upper()

        if not normalized_symbol:
            return False

        return (
            normalized_symbol
            in self._profiles
        )

    def list_symbols(
        self,
    ) -> list[str]:
        return sorted(
            self._profiles.keys()
        )
