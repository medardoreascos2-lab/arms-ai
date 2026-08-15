from dataclasses import dataclass
from typing import List



@dataclass
class LearningReport:

    trades_analyzed: int

    win_rate: float

    total_profit: float

    performance_level: str

    insights: List[str]

    recommendations: List[str]





class AILearningEngine:


    def __init__(self):
        pass



    def analyze(

        self,

        trades: List,

    ) -> LearningReport:



        total = len(trades)


        if total == 0:

            return LearningReport(

                trades_analyzed=0,

                win_rate=0,

                total_profit=0,

                performance_level="NO DATA",

                insights=[
                    "No existen operaciones para analizar."
                ],

                recommendations=[],

            )



        profits = []


        for trade in trades:

            profits.append(

                getattr(
                    trade,
                    "profit",
                    0
                )

            )



        wins = len(

            [

                p for p in profits

                if p > 0

            ]

        )



        total_profit = sum(
            profits
        )


        win_rate = round(

            (wins / total) * 100,

            2

        )



        insights = []

        recommendations = []



        if win_rate >= 60:

            performance = "STRONG"

            insights.append(
                "La estrategia muestra consistencia positiva."
            )


        elif win_rate >= 40:

            performance = "MODERATE"

            insights.append(
                "La estrategia tiene rendimiento mixto."
            )


        else:

            performance = "WEAK"

            insights.append(
                "La estrategia requiere optimización."
            )



        if total_profit > 0:

            recommendations.append(
                "Mantener gestión de riesgo actual."
            )

        else:

            recommendations.append(
                "Revisar entradas y condiciones del mercado."
            )



        return LearningReport(

            trades_analyzed=total,

            win_rate=win_rate,

            total_profit=total_profit,

            performance_level=performance,

            insights=insights,

            recommendations=recommendations,

        )
