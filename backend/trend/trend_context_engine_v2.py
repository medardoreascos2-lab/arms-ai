from dataclasses import dataclass

from backend.indicators.ema_engine import EMAEngine

from backend.market_structure.market_structure_engine_v3 import (
    MarketStructureEngineV3,
)


@dataclass
class TrendContextResultV2:

    trend_1h: str

    trend_15m: str

    structure_1h: str

    structure_15m: str

    aligned: bool

    allowed_direction: str

    score: float



class TrendContextEngineV2:


    def __init__(self):

        self.market_structure = (
            MarketStructureEngineV3()
        )



    def analyze(
        self,
        candles_1h,
        candles_15m,
    ) -> TrendContextResultV2:


        structure_1h = (
            self.market_structure.analyze(
                candles_1h
            )
        )


        structure_15m = (
            self.market_structure.analyze(
                candles_15m
            )
        )



        trend_1h = (
            structure_1h.trend
        )

        trend_15m = (
            structure_15m.trend
        )



        score = 0

        direction = "NONE"

        aligned = False



        if trend_1h == "BULLISH":

            score += 30


        if trend_1h == "BEARISH":

            score += 30



        if trend_15m == "BULLISH":

            score += 30


        if trend_15m == "BEARISH":

            score += 30



        if structure_1h.bos:

            score += 20


        if structure_15m.bos:

            score += 20



        if (
            trend_1h == "BULLISH"
            and trend_15m == "BULLISH"
        ):

            aligned = True

            direction = "LONG"



        elif (
            trend_1h == "BEARISH"
            and trend_15m == "BEARISH"
        ):

            aligned = True

            direction = "SHORT"



        return TrendContextResultV2(

            trend_1h=trend_1h,

            trend_15m=trend_15m,

            structure_1h=structure_1h.structure,

            structure_15m=structure_15m.structure,

            aligned=aligned,

            allowed_direction=direction,

            score=min(
                score,
                100,
            ),
        )
