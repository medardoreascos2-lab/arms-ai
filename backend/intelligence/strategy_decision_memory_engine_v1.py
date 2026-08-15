class StrategyDecisionMemoryEngineV1:
    """
    Memoria histórica de decisiones
    estratégicas de ARMS AI.
    """


    def __init__(self):

        self.memory = []


    def record_decision(
        self,
        strategy: str,
        decision: str,
        market_context: str,
        confidence: str,
    ):

        record = {

            "strategy": strategy,

            "decision": decision,

            "market_context": market_context,

            "confidence": confidence,

            "result": None,

            "learned": False,

        }


        self.memory.append(
            record
        )


        return record



    def update_result(
        self,
        index: int,
        result: str,
    ):

        if index >= len(self.memory):

            return None


        self.memory[index]["result"] = result


        self.memory[index]["learned"] = True


        return self.memory[index]



    def history(self):

        return self.memory



    def strategy_performance(
        self,
        strategy: str,
    ):


        records = [

            item

            for item in self.memory

            if item["strategy"] == strategy

        ]


        total = len(records)


        wins = sum(

            1

            for item in records

            if item["result"] == "WIN"

        )


        losses = sum(

            1

            for item in records

            if item["result"] == "LOSS"

        )


        win_rate = (

            wins / total * 100

            if total

            else 0

        )


        return {

            "strategy": strategy,

            "decisions": total,

            "wins": wins,

            "losses": losses,

            "win_rate": round(
                win_rate,
                2,
            ),

        }
