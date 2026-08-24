from backend.backtesting.strategy_intelligence_orchestrator_v2 import (
    StrategyIntelligenceOrchestratorV2,
)


class FakeRankingService:

    def get_ranking(self):
        return {
            "status": "OK",
            "ranking": [
                {
                    "strategy_id": "STR-001",
                    "strategy_name": "EMA50 Smart Money",
                    "ranking_score": 95,
                },
                {
                    "strategy_id": "STR-002",
                    "strategy_name": "Breakout",
                    "ranking_score": 70,
                },
            ],
        }


class FakeRecommendationService:

    def recommend(self, *, market_context):
        return {
            "strategy_id": "STR-001",
            "strategy_name": "EMA50 Smart Money",
            "confidence": 95,
        }


class FakeSelectionService:

    def select(self, *, market_context):
        return {
            "strategy_id": "STR-001",
            "strategy_name": "EMA50 Smart Money",
            "confidence": 95,
        }


class FakeDecisionService:

    def get_decision(self, *, market_context):
        return {
            "decision": "EXECUTE",
            "strategy_id": "STR-001",
            "confidence": 95,
        }


def build_orchestrator(
    *,
    ranking_service=None,
    recommendation_service=None,
    selection_service=None,
    decision_service=None,
):
    return StrategyIntelligenceOrchestratorV2(
        ranking_service=(
            ranking_service
            if ranking_service is not None
            else FakeRankingService()
        ),
        recommendation_service=(
            recommendation_service
            if recommendation_service is not None
            else FakeRecommendationService()
        ),
        selection_service=(
            selection_service
            if selection_service is not None
            else FakeSelectionService()
        ),
        decision_service=(
            decision_service
            if decision_service is not None
            else FakeDecisionService()
        ),
    )


def test_orchestrator_returns_complete_intelligence_result():

    orchestrator = build_orchestrator()

    result = orchestrator.analyze(
        market_context={
            "trend": "BULLISH",
            "structure": "BREAKOUT",
            "regime": "TRENDING",
            "volatility": "LOW_VOLATILITY",
        }
    )

    assert result["status"] == "OK"

    assert result["ranking"]["ranking"][0]["strategy_id"] == (
        "STR-001"
    )

    assert result["recommendation"]["strategy_id"] == (
        "STR-001"
    )

    assert result["selection"]["strategy_id"] == (
        "STR-001"
    )

    assert result["decision"]["decision"] == (
        "EXECUTE"
    )


def test_orchestrator_preserves_market_context():

    context = {
        "trend": "BEARISH",
        "structure": "CHOCH",
        "regime": "TRENDING",
        "volatility": "HIGH_VOLATILITY",
    }

    class RecordingDecisionService:

        def __init__(self):
            self.received_context = None

        def get_decision(self, *, market_context):
            self.received_context = market_context

            return {
                "decision": "BLOCK",
                "strategy_id": None,
                "confidence": 0,
            }

    decision_service = RecordingDecisionService()

    orchestrator = build_orchestrator(
        decision_service=decision_service,
    )

    result = orchestrator.analyze(
        market_context=context
    )

    assert (
        decision_service.received_context
        == context
    )

    assert result["market_context"] == context


def test_orchestrator_blocks_when_decision_is_blocked():

    class BlockedDecisionService:

        def get_decision(self, *, market_context):
            return {
                "status": "BLOCKED",
                "reason": "NO_SELECTED_STRATEGY",
            }

    orchestrator = build_orchestrator(
        decision_service=BlockedDecisionService(),
    )

    result = orchestrator.analyze(
        market_context={}
    )

    assert result["status"] == "BLOCKED"

    assert result["decision"]["status"] == (
        "BLOCKED"
    )

    assert result["decision"]["reason"] == (
        "NO_SELECTED_STRATEGY"
    )


def test_orchestrator_requires_services():

    try:
        StrategyIntelligenceOrchestratorV2(
            ranking_service=None,
            recommendation_service=None,
            selection_service=None,
            decision_service=None,
        )
    except TypeError:
        return

    raise AssertionError(
        "El orquestador debe exigir sus servicios."
    )


def test_orchestrator_executes_services_in_contract():

    calls = []

    class RankingService:

        def get_ranking(self):
            calls.append("ranking")
            return {
                "status": "OK",
                "ranking": [],
            }

    class RecommendationService:

        def recommend(self, *, market_context):
            calls.append("recommendation")
            return {
                "strategy_id": "STR-001",
            }

    class SelectionService:

        def select(self, *, market_context):
            calls.append("selection")
            return {
                "strategy_id": "STR-001",
            }

    class DecisionService:

        def get_decision(self, *, market_context):
            calls.append("decision")
            return {
                "decision": "EXECUTE",
                "strategy_id": "STR-001",
            }

    orchestrator = StrategyIntelligenceOrchestratorV2(
        ranking_service=RankingService(),
        recommendation_service=RecommendationService(),
        selection_service=SelectionService(),
        decision_service=DecisionService(),
    )

    result = orchestrator.analyze(
        market_context={
            "trend": "BULLISH",
        }
    )

    assert result["status"] == "OK"

    assert calls == [
        "ranking",
        "recommendation",
        "selection",
        "decision",
    ]
