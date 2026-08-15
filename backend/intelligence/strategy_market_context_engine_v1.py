class StrategyMarketContextEngineV1:
    """
    Evalúa compatibilidad de estrategias
    según contexto de mercado.
    """


    def __init__(self):

        self.analysis = []


    def evaluate(
        self,
        strategy: str,
        adaptive_score: float,
        market_regime: str,
        volatility: str,
    ) -> dict:


        compatibility = "LOW"


        if market_regime == "TRENDING":

            if volatility == "NORMAL":

                compatibility = "HIGH"

            elif volatility == "HIGH_VOLATILITY":

                compatibility = "MEDIUM"


        elif market_regime == "RANGING":

            compatibility = "LOW"



        if compatibility == "HIGH":

            decision = "KEEP_ACTIVE"

        elif compatibility == "MEDIUM":

            decision = "MONITOR"

        else:

            decision = "PAUSE_STRATEGY"



        result = {

            "strategy": strategy,

            "adaptive_score": adaptive_score,

            "market_regime": market_regime,

            "volatility": volatility,

            "compatibility": compatibility,

            "decision": decision,

        }


        self.analysis.append(
            result
        )


        return result



    def latest(self):

        if not self.analysis:
            return None

        return self.analysis[-1]
