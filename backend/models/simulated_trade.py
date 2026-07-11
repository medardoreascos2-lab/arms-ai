from dataclasses import dataclass
from datetime import datetime


@dataclass
class SimulatedTrade:
    symbol: str
    timeframe: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    contracts: int
    point_value: float
    exit_price: float
    result: str
    pnl: float
    opened_at: datetime
    closed_at: datetime

    def show(self) -> None:
        print("------ SIMULATED TRADE ------")
        print(f"Símbolo: {self.symbol}")
        print(f"Timeframe: {self.timeframe}")
        print(f"Dirección: {self.direction}")
        print(f"Entrada: {self.entry_price:.2f}")
        print(f"Salida: {self.exit_price:.2f}")
        print(f"Stop Loss: {self.stop_loss:.2f}")
        print(f"Take Profit: {self.take_profit:.2f}")
        print(f"Contratos: {self.contracts}")
        print(f"Resultado: {self.result}")
        print(f"P&L: ${self.pnl:.2f}")