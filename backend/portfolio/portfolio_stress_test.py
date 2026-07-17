from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from backend.portfolio.portfolio import (
    Portfolio,
)


@dataclass(frozen=True)
class PortfolioStressTest:
    """
    Evalúa el impacto de shocks globales o específicos
    por activo sobre el valor de mercado del portafolio.
    """

    initial_market_value: float
    stressed_market_value: float
    absolute_change: float
    change_percent: float
    impacts: Mapping[str, float]
    worst_affected_asset: str | None
    worst_asset_impact: float

    @classmethod
    def run(
        cls,
        *,
        portfolio: Portfolio,
        global_shock: float | None = None,
        shocks: dict[str, float] | None = None,
    ) -> "PortfolioStressTest":
        if not isinstance(
            portfolio,
            Portfolio,
        ):
            raise TypeError(
                "portfolio debe ser Portfolio."
            )

        normalized_shocks = {
            symbol.strip().upper(): float(value)
            for symbol, value in (shocks or {}).items()
        }

        if global_shock is None and not normalized_shocks:
            raise ValueError(
                "Debe proporcionarse al menos un shock."
            )

        if global_shock is not None:
            global_shock = float(global_shock)
            cls._validate_shock(
                global_shock
            )

        for shock in normalized_shocks.values():
            cls._validate_shock(
                shock
            )

        initial_market_value = float(
            portfolio.total_market_value
        )

        impacts: dict[str, float] = {}

        for position in portfolio.positions:
            shock = normalized_shocks.get(
                position.symbol,
                global_shock if global_shock is not None else 0.0,
            )

            signed_market_value = (
                position.quantity
                * position.current_price
            )

            impact = (
                signed_market_value
                * shock
            )

            impacts[position.symbol] = round(
                impact,
                2,
            )

        absolute_change = round(
            sum(impacts.values()),
            2,
        )

        stressed_market_value = round(
            initial_market_value
            + absolute_change,
            2,
        )

        if initial_market_value == 0:
            change_percent = 0.0
        else:
            change_percent = round(
                absolute_change
                / initial_market_value
                * 100,
                2,
            )

        if impacts:
            worst_affected_asset = min(
                impacts,
                key=impacts.get,
            )
            worst_asset_impact = impacts[
                worst_affected_asset
            ]
        else:
            worst_affected_asset = None
            worst_asset_impact = 0.0

        return cls(
            initial_market_value=round(
                initial_market_value,
                2,
            ),
            stressed_market_value=stressed_market_value,
            absolute_change=absolute_change,
            change_percent=change_percent,
            impacts=MappingProxyType(
                dict(impacts)
            ),
            worst_affected_asset=worst_affected_asset,
            worst_asset_impact=worst_asset_impact,
        )

    @staticmethod
    def _validate_shock(
        shock: float,
    ) -> None:
        if shock < -1 or shock > 1:
            raise ValueError(
                "shock debe estar entre -1 y 1."
            )
