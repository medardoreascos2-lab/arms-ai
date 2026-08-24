from typing import Any


class StrategyIntelligenceOrchestratorV2:
    """
    Orquesta el flujo de inteligencia de estrategias:

        ranking
            ↓
        recommendation
            ↓
        selection
            ↓
        decision

    El orquestador coordina los servicios existentes.
    No implementa lógica propia de ranking, selección
    o decisión.
    """

    def __init__(
        self,
        *,
        ranking_service: Any,
        recommendation_service: Any,
        selection_service: Any,
        decision_service: Any,
    ) -> None:

        if ranking_service is None:
            raise TypeError(
                "ranking_service es requerido."
            )

        if recommendation_service is None:
            raise TypeError(
                "recommendation_service es requerido."
            )

        if selection_service is None:
            raise TypeError(
                "selection_service es requerido."
            )

        if decision_service is None:
            raise TypeError(
                "decision_service es requerido."
            )

        self.ranking_service = ranking_service
        self.recommendation_service = (
            recommendation_service
        )
        self.selection_service = selection_service
        self.decision_service = decision_service

    def analyze(
        self,
        *,
        market_context: dict[str, Any],
    ) -> dict[str, Any]:

        ranking = self.ranking_service.get_ranking()

        recommendation = (
            self.recommendation_service.recommend(
                market_context=market_context,
            )
        )

        selection = (
            self.selection_service.select(
                market_context=market_context,
            )
        )

        decision = (
            self.decision_service.get_decision(
                market_context=market_context,
            )
        )

        decision_status = decision.get(
            "status"
        )

        if decision_status == "BLOCKED":
            status = "BLOCKED"
        else:
            status = "OK"

        return {
            "status": status,
            "market_context": market_context,
            "ranking": ranking,
            "recommendation": recommendation,
            "selection": selection,
            "decision": decision,
        }
