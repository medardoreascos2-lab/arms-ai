from dataclasses import dataclass
from typing import List



@dataclass
class TradeOutcomeReport:

    trade_id: str

    symbol: str

    result: str

    pnl: float

    points: float

    performance: str

    insights: List[str]




class TradeOutcomeAnalyzerV2:



    def __init__(self):

        pass



    def analyze(

        self,

        trade_id: str,

        symbol: str,

        direction: str,

        entry: float,

        exit_price: float,

        contracts: int,

        real_pnl: float | None = None,

    ) -> TradeOutcomeReport:



        insights = []



        if direction == "BUY":

            points = exit_price - entry

        else:

            points = entry - exit_price



        pnl = (
            float(real_pnl)
            if real_pnl is not None
            else points * contracts * 20
        )



        if pnl > 0:

            result = "WIN"

            performance = "POSITIVE"

            insights.append(

                "La operación alcanzó resultado favorable."

            )


        elif pnl < 0:

            result = "LOSS"

            performance = "NEGATIVE"

            insights.append(

                "La operación terminó en pérdida."

            )


        else:

            result = "BREAKEVEN"

            performance = "NEUTRAL"

            insights.append(

                "La operación terminó sin ganancia ni pérdida."

            )



        insights.append(

            f"Dirección analizada: {direction}"

        )


        insights.append(

            f"Puntos obtenidos: {points}"

        )



        return TradeOutcomeReport(

            trade_id=trade_id,

            symbol=symbol,

            result=result,

            pnl=pnl,

            points=points,

            performance=performance,

            insights=insights,

        )
