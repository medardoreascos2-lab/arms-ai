from dataclasses import dataclass


@dataclass(frozen=True)
class EquityPoint:
    trade_number: int
    pnl: float
    balance: float
    peak_balance: float
    drawdown: float


class EquityCurve:
    """
    Registra la evolución del capital operación por operación.
    """

    def __init__(
        self,
        initial_balance: float,
    ) -> None:
        if initial_balance <= 0:
            raise ValueError(
                "initial_balance debe ser mayor que cero."
            )

        self.initial_balance = float(initial_balance)
        self.balance = float(initial_balance)
        self.peak_balance = float(initial_balance)
        self.max_drawdown = 0.0
        self.points: list[EquityPoint] = []

    def add_trade(
        self,
        pnl: float,
    ) -> EquityPoint:
        self.balance += float(pnl)

        if self.balance > self.peak_balance:
            self.peak_balance = self.balance

        drawdown = self.peak_balance - self.balance

        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

        point = EquityPoint(
            trade_number=len(self.points) + 1,
            pnl=float(pnl),
            balance=self.balance,
            peak_balance=self.peak_balance,
            drawdown=drawdown,
        )

        self.points.append(point)

        return point
