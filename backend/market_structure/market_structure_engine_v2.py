from dataclasses import dataclass


@dataclass
class MarketStructureResultV2:
    trend: str
    bos: bool
    choch: bool
    swing_high: float | None
    swing_low: float | None
    score: float


class MarketStructureEngineV2:
    """
    Motor básico de estructura de mercado ARMS AI.

    Detecta:
    - Swing High
    - Swing Low
    - BOS
    - CHOCH
    """


    def analyze(
        self,
        candles,
    ) -> MarketStructureResultV2:


        if len(candles) < 5:
            return MarketStructureResultV2(
                trend="UNKNOWN",
                bos=False,
                choch=False,
                swing_high=None,
                swing_low=None,
                score=0.0,
            )


        highs = [
            candle["high"]
            if isinstance(candle, dict)
            else candle.high
            for candle in candles
        ]


        lows = [
            candle["low"]
            if isinstance(candle, dict)
            else candle.low
            for candle in candles
        ]


        current_high = highs[-1]
        current_low = lows[-1]


        previous_high = max(
            highs[:-1]
        )

        previous_low = min(
            lows[:-1]
        )


        bos = False
        choch = False


        trend = "RANGE"

        score = 0


        if current_high > previous_high:

            bos = True
            trend = "BULLISH"
            score += 30


        elif current_low < previous_low:

            bos = True
            trend = "BEARISH"
            score += 30



        if len(highs) >= 3:

            if (
                highs[-1] > highs[-2]
                and lows[-1] > lows[-2]
            ):
                trend = "BULLISH"



            if (
                highs[-1] < highs[-2]
                and lows[-1] < lows[-2]
            ):
                trend = "BEARISH"



        if trend == "BULLISH":
            score += 20


        if trend == "BEARISH":
            score += 20


        return MarketStructureResultV2(
            trend=trend,
            bos=bos,
            choch=choch,
            swing_high=previous_high,
            swing_low=previous_low,
            score=min(
                score,
                50
            ),
        )
