from dataclasses import dataclass, field


@dataclass
class DecisionCouncilResult:
    action: str = "NO_TRADE"
    direction: str = "NEUTRAL"
    grade: str = "NO OPERAR"

    approved: bool = False
    probability: float = 0.0
    confidence: str = "BAJA"

    confluence_score: float = 0.0
    reasoning_score: int = 0

    votes_for: int = 0
    votes_against: int = 0

    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def show(self) -> None:
        print("------ DECISION COUNCIL ------")
        print(f"Acción final: {self.action}")
        print(f"Dirección: {self.direction}")
        print(f"Calificación: {self.grade}")
        print(f"Aprobada: {'SÍ' if self.approved else 'NO'}")
        print(f"Probabilidad: {self.probability:.2f}%")
        print(f"Confianza: {self.confidence}")
        print(f"Confluencia: {self.confluence_score:.2f}/100")
        print(f"Razonamiento: {self.reasoning_score}/100")
        print(f"Votos a favor: {self.votes_for}")
        print(f"Votos en contra: {self.votes_against}")

        if self.reasons:
            print("Motivos:")
            for reason in self.reasons:
                print(f"- {reason}")

        if self.blockers:
            print("Bloqueos:")
            for blocker in self.blockers:
                print(f"- {blocker}")

        if self.warnings:
            print("Advertencias:")
            for warning in self.warnings:
                print(f"- {warning}")
