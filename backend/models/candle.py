from dataclasses import dataclass
from datetime import datetime


@dataclass
class Candle:
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: datetime

    def show(self) -> None:
        print("------ CANDLE ------")
        print(f"Símbolo: {self.symbol}")
        print(f"Timeframe: {self.timeframe}")
        print(f"Open: {self.open}")
        print(f"High: {self.high}")
        print(f"Low: {self.low}")
        print(f"Close: {self.close}")
        print(f"Volumen: {self.volume}")
        print(f"Hora: {self.timestamp}")