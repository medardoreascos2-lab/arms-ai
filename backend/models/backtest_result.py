from dataclasses import dataclass, field
from typing import Any

from backend.backtesting.equity_curve import EquityCurve
from backend.models.backtest_statistics import BacktestStatistics


@dataclass
class BacktestResult:
    total_candles: int = 0
    total_signals: int = 0
    authorized_trades: int = 0
    blocked_signals: int = 0
    initial_balance: float = 17000.0
    trades: list[Any] = field(
        default_factory=list
    )
    statistics: BacktestStatistics = field(
        default_factory=BacktestStatistics
    )
    equity_curve: EquityCurve = field(
        init=False
    )

    def __post_init__(self) -> None:
        if self.initial_balance <= 0:
            raise ValueError(
                "initial_balance debe ser mayor que cero."
            )

        self.equity_curve = EquityCurve(
            initial_balance=self.initial_balance,
        )

    def show(self) -> None:
        print("------ BACKTEST RESULT ------")
        print(f"Velas procesadas: {self.total_candles}")
        print(f"Señales evaluadas: {self.total_signals}")
        print(f"Operaciones autorizadas: {self.authorized_trades}")
        print(f"Señales bloqueadas: {self.blocked_signals}")
        print(f"Operaciones registradas: {len(self.trades)}")
        print(
            f"Balance final: "
            f"${self.equity_curve.balance:.2f}"
        )
        print(
            f"Pico de capital: "
            f"${self.equity_curve.peak_balance:.2f}"
        )
        print(
            f"Drawdown máximo: "
            f"${self.equity_curve.max_drawdown:.2f}"
        )

        self.statistics.show()
