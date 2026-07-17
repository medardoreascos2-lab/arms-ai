from dataclasses import dataclass

from backend.portfolio.portfolio_position import (
    PortfolioPosition,
)


@dataclass(frozen=True)
class Portfolio:
    """
    Agrupa posiciones y calcula métricas agregadas
    de exposición y rendimiento.
    """

    positions: tuple[PortfolioPosition, ...]

    def __init__(
        self,
        positions: list[PortfolioPosition]
        | tuple[PortfolioPosition, ...],
    ) -> None:
        normalized_positions = tuple(
            positions
        )

        for position in normalized_positions:
            if not isinstance(
                position,
                PortfolioPosition,
            ):
                raise TypeError(
                    "positions debe contener "
                    "PortfolioPosition."
                )

        symbols = [
            position.symbol
            for position in normalized_positions
        ]

        if len(symbols) != len(set(symbols)):
            raise ValueError(
                "duplicate symbols no están permitidos."
            )

        object.__setattr__(
            self,
            "positions",
            normalized_positions,
        )

    @property
    def total_positions(self) -> int:
        return len(self.positions)

    @property
    def total_cost_basis(self) -> float:
        return round(
            sum(
                position.cost_basis
                for position in self.positions
            ),
            2,
        )

    @property
    def total_market_value(self) -> float:
        return round(
            sum(
                position.market_value
                for position in self.positions
            ),
            2,
        )

    @property
    def total_unrealized_pnl(self) -> float:
        return round(
            sum(
                position.unrealized_pnl
                for position in self.positions
            ),
            2,
        )

    @property
    def long_exposure(self) -> float:
        return round(
            sum(
                position.market_value
                for position in self.positions
                if position.side == "long"
            ),
            2,
        )

    @property
    def short_exposure(self) -> float:
        return round(
            sum(
                position.market_value
                for position in self.positions
                if position.side == "short"
            ),
            2,
        )

    @property
    def gross_exposure(self) -> float:
        return round(
            self.long_exposure
            + self.short_exposure,
            2,
        )

    @property
    def net_exposure(self) -> float:
        return round(
            self.long_exposure
            - self.short_exposure,
            2,
        )

    @property
    def weights(self) -> dict[str, float]:
        if self.gross_exposure == 0:
            return {}

        return {
            position.symbol: round(
                position.market_value
                / self.gross_exposure
                * 100,
                2,
            )
            for position in self.positions
            if position.market_value > 0
        }
