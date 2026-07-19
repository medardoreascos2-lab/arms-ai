from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class PortfolioRebalancingEngine:
    """
    Calcula las operaciones necesarias para mover
    un portafolio desde pesos actuales a pesos objetivo.
    """

    assets: tuple[str, ...]
    current_weights: Mapping[str, float]
    target_weights: Mapping[str, float]
    trades: Mapping[str, float]
    turnover: float
    overweight_assets: tuple[str, ...]
    underweight_assets: tuple[str, ...]
    tolerance: float

    @classmethod
    def rebalance(
        cls,
        *,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
        tolerance: float = 0.0,
    ) -> "PortfolioRebalancingEngine":
        if tolerance < 0:
            raise ValueError(
                "tolerance no puede ser negativa."
            )

        normalized_current = {
            symbol.strip().upper(): float(value)
            for symbol, value in current_weights.items()
        }

        normalized_target = {
            symbol.strip().upper(): float(value)
            for symbol, value in target_weights.items()
        }

        if set(normalized_current) != set(
            normalized_target
        ):
            raise ValueError(
                "current_weights y target_weights "
                "deben contener los mismos assets."
            )

        if not normalized_current:
            raise ValueError(
                "weights no puede estar vacío."
            )

        assets = tuple(
            normalized_current
        )

        trades: dict[str, float] = {}

        for asset in assets:
            difference = (
                normalized_target[asset]
                - normalized_current[asset]
            )

            if abs(difference) <= tolerance:
                trade = 0.0
            else:
                trade = round(
                    difference,
                    6,
                )

            trades[asset] = trade

        overweight_assets = tuple(
            asset
            for asset in assets
            if trades[asset] < 0
        )

        underweight_assets = tuple(
            asset
            for asset in assets
            if trades[asset] > 0
        )

        turnover = round(
            sum(
                abs(trade)
                for trade in trades.values()
            )
            / 2.0,
            6,
        )

        return cls(
            assets=assets,
            current_weights=MappingProxyType(
                dict(normalized_current)
            ),
            target_weights=MappingProxyType(
                dict(normalized_target)
            ),
            trades=MappingProxyType(
                dict(trades)
            ),
            turnover=turnover,
            overweight_assets=overweight_assets,
            underweight_assets=underweight_assets,
            tolerance=float(tolerance),
        )
