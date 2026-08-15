from dataclasses import dataclass
from typing import List


@dataclass
class MemoryScoreReport:

    trades_analyzed: int

    win_rate: float

    historical_score: float

    reliability: str

    adjustment: float

    insights: List[str]

    recommendations: List[str]



class MemoryScoringEngine:


    def __init__(self):
        pass



    def calculate(
        self,
        trades
    ) -> MemoryScoreReport:


        total = len(trades)


        if total == 0:

            return MemoryScoreReport(

                trades_analyzed=0,

                win_rate=0,

                historical_score=0,

                reliability="NO DATA",

                adjustment=0,

                insights=[
                    "No existe historial suficiente."
                ],

                recommendations=[
                    "Esperar más operaciones."
                ],

            )



        winners = 0


        for trade in trades:

            profit = getattr(
                trade,
                "profit",
                0
            )

            if profit > 0:

                winners += 1



        win_rate = (
            winners / total
        ) * 100



        historical_score = min(
            100,
            win_rate
        )



        if historical_score >= 80:

            reliability = "HIGH"

            adjustment = 5


        elif historical_score >= 60:

            reliability = "MEDIUM"

            adjustment = 2


        else:

            reliability = "LOW"

            adjustment = -5



        insights = [

            f"Win rate histórico: {win_rate:.2f}%.",

            f"Confiabilidad de memoria: {reliability}.",

        ]


        recommendations = []


        if adjustment > 0:

            recommendations.append(
                "Aumentar confianza usando memoria histórica."
            )

        else:

            recommendations.append(
                "Reducir confianza hasta mejorar resultados."
            )



        return MemoryScoreReport(

            trades_analyzed=total,

            win_rate=round(
                win_rate,
                2
            ),

            historical_score=round(
                historical_score,
                2
            ),

            reliability=reliability,

            adjustment=adjustment,

            insights=insights,

            recommendations=recommendations,

        )
