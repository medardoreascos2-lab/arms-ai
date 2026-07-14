from dataclasses import dataclass


@dataclass
class BacktestResult:
    total_candles: int = 0
    total_signals: int = 0
    authorized_trades: int = 0
    blocked_signals: int = 0

    def show(self) -> None:
        print("------ BACKTEST RESULT ------")
        print(f"Velas procesadas: {self.total_candles}")
        print(f"Señales evaluadas: {self.total_signals}")
        print(f"Operaciones autorizadas: {self.authorized_trades}")
        print(f"Señales bloqueadas: {self.blocked_signals}")
