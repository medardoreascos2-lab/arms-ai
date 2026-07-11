from dataclasses import dataclass, field


@dataclass
class TradePlan:
    symbol: str
    timeframe: str
    decision: str
    confidence: str
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    contracts: int
    risk_amount: float
    authorized: bool
    reasons: list[str] = field(default_factory=list)

    def show(self) -> None:
        print("------ TRADE PLAN ------")
        print(f"Símbolo: {self.symbol}")
        print(f"Timeframe: {self.timeframe}")
        print(f"Decisión: {self.decision}")
        print(f"Confianza: {self.confidence}")
        print(f"Operación autorizada: {'SÍ' if self.authorized else 'NO'}")
        print(f"Contratos: {self.contracts}")
        print(f"Riesgo máximo: ${self.risk_amount:.2f}")

        if self.entry_price is not None:
            print(f"Entrada: {self.entry_price:.2f}")

        if self.stop_loss is not None:
            print(f"Stop Loss: {self.stop_loss:.2f}")

        if self.take_profit is not None:
            print(f"Take Profit: {self.take_profit:.2f}")

        if self.reasons:
            print("Motivos:")
            for reason in self.reasons:
                print(f"- {reason}")