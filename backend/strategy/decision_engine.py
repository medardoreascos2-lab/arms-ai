from dataclasses import dataclass


@dataclass
class DecisionResult:
    decision: str


class DecisionEngine:

    def __init__(self):
        self.decision = "ESPERAR"
        self.result = DecisionResult(
            decision="ESPERAR"
        )

    def analyze(
        self,
        intelligence_recommendation: str,
    ) -> DecisionResult:

        valid_decisions = {
            "BUSCAR COMPRAS",
            "BUSCAR VENTAS",
            "ESPERAR",
        }

        if intelligence_recommendation not in valid_decisions:
            raise ValueError(
                f"Recomendación no válida: {intelligence_recommendation}"
            )

        self.decision = intelligence_recommendation

        self.result = DecisionResult(
            decision=self.decision
        )

        return self.result

    def show(self) -> None:
        print("------ DECISION ENGINE ------")
        print(
            f"Decisión final: {self.result.decision}"
        )
