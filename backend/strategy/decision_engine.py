class DecisionEngine:
    def __init__(self):
        self.decision = "ESPERAR"

    def analyze(self, intelligence_recommendation: str) -> str:
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
        return self.decision

    def show(self) -> None:
        print("------ DECISION ENGINE ------")
        print(f"Decisión final: {self.decision}")