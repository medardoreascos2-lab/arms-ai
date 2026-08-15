from dataclasses import dataclass
from typing import List, Dict



@dataclass
class TradingMemoryReport:

    total_trades: int

    winning_trades: int

    losing_trades: int

    win_rate: float

    dominant_direction: str

    best_pattern: str

    recommendation: str

    insights: List[str]




class TradingMemoryEngineV2:



    def __init__(self):

        self.history = []



    def analyze_trade(

        self,

        symbol: str,

        direction: str,

        strategy: str,

        result: str,

        pnl: float,

    ):

        trade = {

            "symbol": symbol,

            "direction": direction,

            "strategy": strategy,

            "result": result,

            "pnl": pnl,

        }


        self.history.append(trade)



        return trade




    def analyze_memory(self) -> TradingMemoryReport:


        total = len(
            self.history
        )


        winners = len(

            [

                trade

                for trade in self.history

                if trade["pnl"] > 0

            ]

        )


        losers = len(

            [

                trade

                for trade in self.history

                if trade["pnl"] < 0

            ]

        )


        if total > 0:

            win_rate = round(

                (winners / total) * 100,

                2

            )

        else:

            win_rate = 0



        directions = {}


        for trade in self.history:

            direction = trade["direction"]

            directions[direction] = (

                directions.get(direction, 0)

                +

                1

            )



        if directions:

            dominant_direction = max(

                directions,

                key=directions.get

            )

        else:

            dominant_direction = "NONE"




        patterns = {}


        for trade in self.history:

            strategy = trade["strategy"]

            patterns[strategy] = (

                patterns.get(strategy, 0)

                +

                1

            )



        if patterns:

            best_pattern = max(

                patterns,

                key=patterns.get

            )

        else:

            best_pattern = "NONE"




        insights = []


        if win_rate >= 70:

            insights.append(

                "El patrón histórico muestra alta consistencia."

            )

        else:

            insights.append(

                "Se necesita más información histórica."

            )



        if dominant_direction != "NONE":

            insights.append(

                f"La dirección dominante es {dominant_direction}."

            )



        recommendation = (

            "Mantener estrategia actual."

            if win_rate >= 60

            else

            "Revisar parámetros de entrada."

        )



        return TradingMemoryReport(

            total_trades=total,

            winning_trades=winners,

            losing_trades=losers,

            win_rate=win_rate,

            dominant_direction=dominant_direction,

            best_pattern=best_pattern,

            recommendation=recommendation,

            insights=insights,

        )
