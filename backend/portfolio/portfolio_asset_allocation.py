from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from backend.portfolio.portfolio import (
    Portfolio,
)


@dataclass(frozen=True)
class PortfolioAssetAllocation:
    """
    Resume la distribución del valor de mercado
    por símbolo dentro del portafolio.
    """

    total_market_value: float
    weights: Mapping[str, float]
    ordered_symbols: tuple[str, ...]

    largest_symbol: str | None
    largest_weight: float

    smallest_symbol: str | None
    smallest_weight: float

    top_1_concentration: float
    top_2_concentration: float

    @classmethod
    def from_portfolio(
        cls,
        portfolio: Portfolio,
    ) -> "PortfolioAssetAllocation":
        if not isinstance(
            portfolio,
            Portfolio,
        ):
            raise TypeError(
                "portfolio debe ser Portfolio."
            )

        total_market_value = float(
            portfolio.total_market_value
        )

        if total_market_value == 0:
            return cls(
                total_market_value=0.0,
                weights=MappingProxyType({}),
                ordered_symbols=(),
                largest_symbol=None,
                largest_weight=0.0,
                smallest_symbol=None,
                smallest_weight=0.0,
                top_1_concentration=0.0,
                top_2_concentration=0.0,
            )

        raw_weights = {
            position.symbol: round(
                position.market_value
                / total_market_value
                * 100,
                2,
            )
            for position in portfolio.positions
            if position.market_value > 0
        }

        ordered = tuple(
            sorted(
                raw_weights,
                key=raw_weights.get,
                reverse=True,
            )
        )

        largest_symbol = ordered[0]
        smallest_symbol = ordered[-1]

        largest_weight = raw_weights[
            largest_symbol
        ]
        smallest_weight = raw_weights[
            smallest_symbol
        ]

        top_1_concentration = largest_weight
        top_2_concentration = round(
            sum(
                raw_weights[symbol]
                for symbol in ordered[:2]
            ),
            2,
        )

        return cls(
            total_market_value=round(
                total_market_value,
                2,
            ),
            weights=MappingProxyType(
                dict(raw_weights)
            ),
            ordered_symbols=ordered,
            largest_symbol=largest_symbol,
            largest_weight=largest_weight,
            smallest_symbol=smallest_symbol,
            smallest_weight=smallest_weight,
            top_1_concentration=top_1_concentration,
            top_2_concentration=top_2_concentration,
        )
