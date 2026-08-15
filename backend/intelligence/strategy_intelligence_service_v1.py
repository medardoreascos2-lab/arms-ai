from backend.intelligence.strategy_intelligence_pipeline_v1 import (
    StrategyIntelligencePipelineV1,
)


class StrategyIntelligenceServiceV1:
    """
    Servicio principal de inteligencia estratégica
    de ARMS AI.
    """


    def __init__(self):

        self.pipeline = (
            StrategyIntelligencePipelineV1()
        )


    def analyze_strategy(
        self,
        strategy: str,
        backtest_score: float,
        market_regime: str,
        volatility: str,
    ) -> dict:

        result = (
            self.pipeline.analyze(
                strategy=strategy,
                backtest_score=backtest_score,
                market_regime=market_regime,
                volatility=volatility,
            )
        )


        decision = (
            result["decision"]
        )


        market = (
            result["market"]
        )


        adaptive = (
            result["adaptive"]
        )


        learning = (
            result["learning"]
        )


        return {

            "strategy": strategy,

            "final_decision": (
                decision["decision"]
            ),

            "confidence": (
                decision["confidence"]
            ),

            "reason": (
                decision["reasons"]
            ),

            "scores": {

                "backtest": (
                    adaptive["backtest_score"]
                ),

                "learning": (
                    adaptive["learning_score"]
                ),

                "final": (
                    adaptive["final_score"]
                ),
            },


            "market": {

                "regime": (
                    market["market_regime"]
                ),

                "volatility": (
                    market["volatility"]
                ),

                "compatibility": (
                    market["compatibility"]
                ),
            },


            "history": {

                "trades": (
                    learning["trades"]
                ),

                "win_rate": (
                    learning["win_rate"]
                ),

            },
        }
