from dataclasses import dataclass
from typing import List


@dataclass
class MemoryReport:

    trades_analyzed: int

    buy_count: int

    sell_count: int

    winning_patterns: List[str]

    losing_patterns: List[str]

    dominant_strategy: str

    memory_quality: str

    insights: List[str]

    recommendations: List[str]



class TradingMemoryEngine:


    def __init__(self):

        pass



    def analyze(
        self,
        trades: List
    ) -> MemoryReport:


        total = len(trades)


        if total == 0:

            return MemoryReport(

                trades_analyzed=0,

                buy_count=0,

                sell_count=0,

                winning_patterns=[],

                losing_patterns=[],

                dominant_strategy="NONE",

                memory_quality="NO DATA",

                insights=[
                    "No existen operaciones para crear memoria."
                ],

                recommendations=[],

            )


        buy_count = 0

        sell_count = 0


        strategies = {}

        winning_patterns = []

        losing_patterns = []



        for trade in trades:


            direction = getattr(
                trade,
                "direction",
                ""
            )


            strategy = getattr(
                trade,
                "strategy",
                "UNKNOWN"
            )


            profit = getattr(
                trade,
                "profit",
                0
            )



            if direction == "BUY":

                buy_count += 1


            elif direction == "SELL":

                sell_count += 1



            strategies[strategy] = (
                strategies.get(strategy, 0) + 1
            )



            if profit > 0:

                winning_patterns.append(
                    f"{direction} - {strategy}"
                )


            elif profit < 0:

                losing_patterns.append(
                    f"{direction} - {strategy}"
                )



        dominant_strategy = max(
            strategies,
            key=strategies.get
        )



        insights = []

        recommendations = []



        insights.append(
            f"Estrategia más utilizada: {dominant_strategy}."
        )


        if winning_patterns:

            insights.append(
                "Existen patrones históricos positivos."
            )


        if losing_patterns:

            insights.append(
                "Existen patrones que requieren revisión."
            )



        if len(winning_patterns) >= len(losing_patterns):

            memory_quality = "GOOD"

            recommendations.append(
                "Usar memoria histórica para validar futuros setups."
            )

        else:

            memory_quality = "REVIEW"

            recommendations.append(
                "Reducir confianza hasta mejorar rendimiento."
            )



        return MemoryReport(

            trades_analyzed=total,

            buy_count=buy_count,

            sell_count=sell_count,

            winning_patterns=winning_patterns,

            losing_patterns=losing_patterns,

            dominant_strategy=dominant_strategy,

            memory_quality=memory_quality,

            insights=insights,

            recommendations=recommendations,

        )
