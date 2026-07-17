from dataclasses import dataclass

from backend.portfolio.portfolio import (
    Portfolio,
)
from backend.portfolio.portfolio_asset_allocation import (
    PortfolioAssetAllocation,
)


@dataclass(frozen=True)
class PortfolioConcentrationReport:
    """
    Analiza el nivel de concentración de un portafolio
    usando pesos por activo e índice Herfindahl.
    """

    top_1_weight: float
    top_2_weight: float
    top_3_weight: float

    herfindahl_index: float
    effective_positions: float
    risk_level: str

    @classmethod
    def from_portfolio(
        cls,
        portfolio: Portfolio,
    ) -> "PortfolioConcentrationReport":
        if not isinstance(
            portfolio,
            Portfolio,
        ):
            raise TypeError(
                "portfolio debe ser Portfolio."
            )

        allocation = (
            PortfolioAssetAllocation.from_portfolio(
                portfolio
            )
        )

        if not allocation.ordered_symbols:
            return cls(
                top_1_weight=0.0,
                top_2_weight=0.0,
                top_3_weight=0.0,
                herfindahl_index=0.0,
                effective_positions=0.0,
                risk_level="none",
            )

        ordered_weights = [
            allocation.weights[symbol]
            for symbol in allocation.ordered_symbols
        ]

        top_1_weight = round(
            sum(ordered_weights[:1]),
            2,
        )
        top_2_weight = round(
            sum(ordered_weights[:2]),
            2,
        )
        top_3_weight = round(
            sum(ordered_weights[:3]),
            2,
        )

        normalized_weights = [
            weight / 100
            for weight in ordered_weights
        ]

        herfindahl_index = sum(
            weight ** 2
            for weight in normalized_weights
        )

        effective_positions = (
            1 / herfindahl_index
            if herfindahl_index > 0
            else 0.0
        )

        if herfindahl_index < 0.15:
            risk_level = "low"
        elif herfindahl_index < 0.25:
            risk_level = "moderate"
        else:
            risk_level = "high"

        return cls(
            top_1_weight=top_1_weight,
            top_2_weight=top_2_weight,
            top_3_weight=top_3_weight,
            herfindahl_index=round(
                herfindahl_index,
                3,
            ),
            effective_positions=round(
                effective_positions,
                2,
            ),
            risk_level=risk_level,
        )
