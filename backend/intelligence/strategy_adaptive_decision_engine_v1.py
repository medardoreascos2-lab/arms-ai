class StrategyAdaptiveDecisionEngineV1:
    """
    Decide estado de estrategia combinando
    backtesting y aprendizaje histórico.
    """


    def __init__(self):

        self.decisions = []


    def evaluate(
        self,
        strategy: str,
        backtest_score: float,
        learning_score: float,
    ) -> dict:


        final_score = (
            backtest_score * 0.5
            +
            learning_score * 0.5
        )


        if final_score >= 45:

            decision = "KEEP_ACTIVE"
            confidence = "HIGH"


        elif final_score >= 35:

            decision = "MONITOR"
            confidence = "MEDIUM"


        else:

            decision = "DISABLE"
            confidence = "LOW"



        result = {

            "strategy": strategy,

            "backtest_score": (
                backtest_score
            ),

            "learning_score": (
                learning_score
            ),

            "final_score": round(
                final_score,
                2,
            ),

            "decision": decision,

            "confidence": confidence,

        }


        self.decisions.append(
            result
        )


        return result



    def best_strategy(self):

        if not self.decisions:
            return None


        return max(
            self.decisions,
            key=lambda x: x["final_score"],
        )
