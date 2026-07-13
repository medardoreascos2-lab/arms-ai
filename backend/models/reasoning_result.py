from dataclasses import dataclass, field


@dataclass
class ReasoningResult:
    direction: str = "ESPERAR"
    grade: str = "NO OPERAR"

    buy_score: int = 0
    sell_score: int = 0
    quality_score: int = 0

    confidence: str = "BAJA"
    authorized: bool = False

    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def show(self) -> None:
        print("------ REASONING RESULT ------")
        print(f"Dirección: {self.direction}")
        print(f"Calificación: {self.grade}")
        print(f"Buy score: {self.buy_score}")
        print(f"Sell score: {self.sell_score}")
        print(f"Quality score: {self.quality_score}")
        print(f"Confianza: {self.confidence}")
        print(f"Autorizada: {self.authorized}")

        if self.reasons:
            print("Motivos:")
            for reason in self.reasons:
                print(f"- {reason}")

        if self.blockers:
            print("Bloqueos:")
            for blocker in self.blockers:
                print(f"- {blocker}")
