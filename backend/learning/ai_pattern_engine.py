from dataclasses import dataclass
from typing import List


@dataclass
class PatternReport:

    trades_analyzed: int

    buy_trades: int

    sell_trades: int

    average_profit: float

    average_loss: float

    best_direction: str

    pattern_quality: str

    insights: List[str]

    recommendations: List[str]



class AIPatternEngine:


    def __init__(self):
        pass



    def analyze(
        self,
        trades: List
    ) -> PatternReport:


        total = len(trades)


        if total == 0:

            return PatternReport(

                trades_analyzed=0,

                buy_trades=0,

                sell_trades=0,

                average_profit=0,

                average_loss=0,

                best_direction="NONE",

                pattern_quality="NO DATA",

                insights=[
                    "No hay operaciones disponibles."
                ],

                recommendations=[],

            )


        buy = 0
        sell = 0

        profits = []
        losses = []


        for trade in trades:

            direction = getattr(
                trade,
                "direction",
                ""
            )


            profit = getattr(
                trade,
                "profit",
                0
            )


            if direction == "BUY":
                buy += 1

            elif direction == "SELL":
                sell += 1


            if profit > 0:
                profits.append(profit)

            elif profit < 0:
                losses.append(profit)



        average_profit = (

            round(
                sum(profits) / len(profits),
                2
            )

            if profits

            else 0

        )


        average_loss = (

            round(
                sum(losses) / len(losses),
                2
            )

            if losses

            else 0

        )



        if buy > sell:

            best_direction = "BUY"

        elif sell > buy:

            best_direction = "SELL"

        else:

            best_direction = "BALANCED"



        insights = []

        recommendations = []



        insights.append(
            f"La dirección dominante es {best_direction}."
        )


        if average_profit > abs(average_loss):

            quality = "GOOD"

            insights.append(
                "Las ganancias promedio superan las pérdidas."
            )

            recommendations.append(
                "Mantener gestión de riesgo actual."
            )

        else:

            quality = "REVIEW"

            recommendations.append(
                "Optimizar entradas y relación riesgo beneficio."
            )



        return PatternReport(

            trades_analyzed=total,

            buy_trades=buy,

            sell_trades=sell,

            average_profit=average_profit,

            average_loss=average_loss,

            best_direction=best_direction,

            pattern_quality=quality,

            insights=insights,

            recommendations=recommendations,

        )
