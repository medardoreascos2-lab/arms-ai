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

    instrument: str = "MNQ"

    probability: float = 0.0
    confluence_score: float = 0.0
    grade: str = ""

    reasons: list[str] = field(
        default_factory=list
    )


    def __post_init__(self) -> None:

        self.probability = float(
            self.probability
        )

        self.confluence_score = float(
            self.confluence_score
        )

        self.grade = (
            str(self.grade)
            .strip()
            .upper()
        )


    def show(self) -> None:

        print("------ TRADE PLAN ------")

        print(
            f"Símbolo: {self.symbol}"
        )

        print(
            f"Timeframe: {self.timeframe}"
        )

        print(
            f"Decisión: {self.decision}"
        )

        print(
            f"Confianza: {self.confidence}"
        )

        print(
            f"Probabilidad: {self.probability}"
        )

        print(
            f"Confluencia: {self.confluence_score}"
        )

        print(
            f"Grade: {self.grade}"
        )

        print(
            f"Operación autorizada: "
            f"{'SÍ' if self.authorized else 'NO'}"
        )

        print(
            f"Contratos: {self.contracts}"
        )

        print(
            f"Riesgo máximo: "
            f"${self.risk_amount:.2f}"
        )


        if self.entry_price is not None:
            print(
                f"Entrada: {self.entry_price:.2f}"
            )


        if self.stop_loss is not None:
            print(
                f"Stop Loss: {self.stop_loss:.2f}"
            )


        if self.take_profit is not None:
            print(
                f"Take Profit: {self.take_profit:.2f}"
            )


        if self.reasons:

            print("Motivos:")

            for reason in self.reasons:
                print(
                    f"- {reason}"
                )
