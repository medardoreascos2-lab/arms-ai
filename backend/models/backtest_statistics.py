from dataclasses import dataclass


@dataclass
class BacktestStatistics:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0

    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0

    win_rate: float = 0.0
    profit_factor: float | None = None
    expectancy: float = 0.0
    max_drawdown: float = 0.0

    def show(self) -> None:
        print("------ BACKTEST STATISTICS ------")
        print(f"Operaciones totales: {self.total_trades}")
        print(f"Operaciones ganadoras: {self.winning_trades}")
        print(f"Operaciones perdedoras: {self.losing_trades}")
        print(f"Operaciones en equilibrio: {self.breakeven_trades}")

        print(f"Ganancia bruta: ${self.gross_profit:.2f}")
        print(f"Pérdida bruta: ${self.gross_loss:.2f}")
        print(f"Beneficio neto: ${self.net_profit:.2f}")

        print(f"Win rate: {self.win_rate:.2f}%")

        if self.profit_factor is None:
            print("Profit factor: N/A")
        else:
            print(f"Profit factor: {self.profit_factor:.2f}")

        print(f"Expectativa por operación: ${self.expectancy:.2f}")
        print(f"Máximo drawdown: ${self.max_drawdown:.2f}")
