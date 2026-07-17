from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioPosition:
    """
    Representa una posición individual dentro de un portafolio.
    """

    symbol: str
    quantity: float
    average_price: float
    current_price: float

    def __post_init__(self) -> None:
        normalized_symbol = self.symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        if self.average_price <= 0:
            raise ValueError(
                "average_price debe ser mayor que cero."
            )

        if self.current_price <= 0:
            raise ValueError(
                "current_price debe ser mayor que cero."
            )

        object.__setattr__(
            self,
            "symbol",
            normalized_symbol,
        )

        object.__setattr__(
            self,
            "quantity",
            float(self.quantity),
        )

        object.__setattr__(
            self,
            "average_price",
            float(self.average_price),
        )

        object.__setattr__(
            self,
            "current_price",
            float(self.current_price),
        )

    @property
    def side(self) -> str:
        if self.quantity > 0:
            return "long"

        if self.quantity < 0:
            return "short"

        return "flat"

    @property
    def cost_basis(self) -> float:
        return round(
            abs(self.quantity)
            * self.average_price,
            2,
        )

    @property
    def market_value(self) -> float:
        return round(
            abs(self.quantity)
            * self.current_price,
            2,
        )

    @property
    def unrealized_pnl(self) -> float:
        if self.quantity == 0:
            return 0.0

        pnl = (
            self.current_price
            - self.average_price
        ) * self.quantity

        return round(
            pnl,
            2,
        )

    @property
    def return_percent(self) -> float:
        if self.cost_basis == 0:
            return 0.0

        return round(
            self.unrealized_pnl
            / self.cost_basis
            * 100,
            2,
        )
