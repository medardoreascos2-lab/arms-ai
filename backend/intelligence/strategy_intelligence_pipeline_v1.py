from backend.intelligence.strategy_learning_engine_v1 import (
    StrategyLearningEngineV1,
)

from backend.intelligence.strategy_adaptive_decision_engine_v1 import (
    StrategyAdaptiveDecisionEngineV1,
)

from backend.intelligence.strategy_market_context_engine_v1 import (
    StrategyMarketContextEngineV1,
)

from backend.intelligence.strategy_autonomous_decision_engine_v1 import (
    StrategyAutonomousDecisionEngineV1,
)

from backend.intelligence.strategy_decision_memory_engine_v1 import (
    StrategyDecisionMemoryEngineV1,
)



class StrategyIntelligencePipelineV1:
    """
    Pipeline completo de inteligencia
    estratégica ARMS AI.
    """


    def __init__(self):

        self.learning_engine = (
            StrategyLearningEngineV1()
        )

        self.adaptive_engine = (
            StrategyAdaptiveDecisionEngineV1()
        )

        self.market_engine = (
            StrategyMarketContextEngineV1()
        )

        self.autonomous_engine = (
            StrategyAutonomousDecisionEngineV1()
        )

        self.memory_engine = (
            StrategyDecisionMemoryEngineV1()
        )


    def analyze(
        self,
        strategy: str,
        backtest_score: float,
        market_regime: str,
        volatility: str,
    ) -> dict:


        learning = (
            self.learning_engine
            .analyze_strategy(strategy)
        )


        adaptive = (
            self.adaptive_engine.evaluate(
                strategy=strategy,
                backtest_score=backtest_score,
                learning_score=learning["learning_score"],
            )
        )


        market = (
            self.market_engine.evaluate(
                strategy=strategy,
                adaptive_score=adaptive["final_score"],
                market_regime=market_regime,
                volatility=volatility,
            )
        )


        decision = (
            self.autonomous_engine.decide(
                strategy=strategy,
                adaptive_score=adaptive["final_score"],
                compatibility=market["compatibility"],
                confidence="HIGH",
            )
        )


        self.memory_engine.record_decision(
            strategy=strategy,
            decision=decision["decision"],
            market_context=market_regime,
            confidence=decision["confidence"],
        )


        return {
            "strategy": strategy,

            "learning": learning,

            "adaptive": adaptive,

            "market": market,

            "decision": decision,

        }
