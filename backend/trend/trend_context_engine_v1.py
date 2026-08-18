from dataclasses import dataclass


@dataclass
class TrendContextResultV1:

    trend_1h: str

    trend_15m: str

    aligned: bool

    allowed_direction: str

    score: float



class TrendContextEngineV1:
    """
    Motor de contexto multi temporal ARMS AI.

    Analiza:

    - Tendencia 1H
    - Tendencia 15M
    - Alineación
    - Dirección permitida
    """


    def analyze(
        self,
        candles_1h,
        candles_15m,
    ) -> TrendContextResultV1:


        trend_1h = self._detect_trend(
            candles_1h
        )


        trend_15m = self._detect_trend(
            candles_15m
        )


        aligned = False

        allowed_direction = "NONE"

        score = 0



        if (
            trend_1h == "BULLISH"
            and trend_15m == "BULLISH"
        ):

            aligned = True

            allowed_direction = "LONG"

            score = 100



        elif (
            trend_1h == "BEARISH"
            and trend_15m == "BEARISH"
        ):

            aligned = True

            allowed_direction = "SHORT"

            score = 100



        elif trend_1h == trend_15m:

            score = 50



        return TrendContextResultV1(

            trend_1h=trend_1h,

            trend_15m=trend_15m,

            aligned=aligned,

            allowed_direction=allowed_direction,

            score=score,

        )



    def _detect_trend(
        self,
        candles,
    ):

        if len(candles) < 5:

            return "UNKNOWN"



        first = (
            candles[0].close
            if hasattr(
                candles[0],
                "close"
            )
            else candles[0]["close"]
        )


        last = (
            candles[-1].close
            if hasattr(
                candles[-1],
                "close"
            )
            else candles[-1]["close"]
        )



        if last > first:

            return "BULLISH"


        if last < first:

            return "BEARISH"


        return "RANGE"
