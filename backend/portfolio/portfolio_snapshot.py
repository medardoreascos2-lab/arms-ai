from dataclasses import dataclass
from datetime import datetime

from backend.portfolio.portfolio import (
    Portfolio,
)
from backend.portfolio.portfolio_position import (
    PortfolioPosition,
)


@dataclass(frozen=True)
class PortfolioSnapshot:
    """
    Representa una captura inmutable del estado
    de un portafolio en un momento específico.
    """

    timestamp: datetime
    portfolio: Portfolio
    cash: float

    def __post_init__(self) -> None:
        if not isinstance(
            self.timestamp,
            datetime,
        ):
            raise TypeError(
                "timestamp debe ser datetime."
            )

        if not isinstance(
            self.portfolio,
            Portfolio,
        ):
            raise TypeError(
                "portfolio debe ser Portfolio."
            )

        if self.cash < 0:
            raise ValueError(
                "cash no puede ser negativo."
            )

        object.__setattr__(
            self,
            "cash",
            float(self.cash),
        )

    @property
    def positions(
        self,
    ) -> tuple[PortfolioPosition, ...]:
        return self.portfolio.positions

    @property
    def total_positions(self) -> int:
        return self.portfolio.total_positions

    @property
    def market_value(self) -> float:
        return self.portfolio.total_market_value

    @property
    def unrealized_pnl(self) -> float:
        return self.portfolio.total_unrealized_pnl

    @property
    def gross_exposure(self) -> float:
        return self.portfolio.gross_exposure

    @property
    def net_exposure(self) -> float:
        return self.portfolio.net_exposure

    @property
    def equity(self) -> float:
        return round(
            self.cash
            + self.market_value,
            2,
        )
