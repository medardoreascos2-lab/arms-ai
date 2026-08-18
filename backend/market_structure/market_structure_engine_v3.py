from dataclasses import dataclass


@dataclass
class MarketStructureResultV3:

    trend: str

    structure: str

    bos: bool

    choch: bool

    swing_high: float | None

    swing_low: float | None

    score: float



class MarketStructureEngineV3:
    """
    Motor avanzado de estructura ARMS AI.

    Detecta:

    - Swing High
    - Swing Low
    - HH
    - HL
    - LH
    - LL
    - BOS
    - CHOCH
    """


    def analyze(
        self,
        candles,
    ) -> MarketStructureResultV3:


        if len(candles) < 10:

            return MarketStructureResultV3(
                trend="UNKNOWN",
                structure="NONE",
                bos=False,
                choch=False,
                swing_high=None,
                swing_low=None,
                score=0.0,
            )


        highs = [
            candle.high
            if hasattr(candle, "high")
            else candle["high"]
            for candle in candles
        ]


        lows = [
            candle.low
            if hasattr(candle, "low")
            else candle["low"]
            for candle in candles
        ]


        swing_highs = []
        swing_lows = []


        for i in range(
            2,
            len(candles)-2,
        ):

            if (
                highs[i] > highs[i-1]
                and highs[i] > highs[i+1]
            ):
                swing_highs.append(
                    highs[i]
                )


            if (
                lows[i] < lows[i-1]
                and lows[i] < lows[i+1]
            ):
                swing_lows.append(
                    lows[i]
                )


        if len(swing_highs) < 2 or len(swing_lows) < 2:

            return MarketStructureResultV3(
                trend="RANGE",
                structure="NO_SWINGS",
                bos=False,
                choch=False,
                swing_high=None,
                swing_low=None,
                score=20,
            )


        last_high = swing_highs[-1]
        previous_high = swing_highs[-2]

        last_low = swing_lows[-1]
        previous_low = swing_lows[-2]


        structure = "RANGE"

        trend = "RANGE"

        bos = False

        choch = False

        score = 0



        # Estructura alcista HH + HL

        if (
            last_high > previous_high
            and last_low > previous_low
        ):

            trend = "BULLISH"

            structure = "HH_HL"

            score += 50



        # Estructura bajista LH + LL

        elif (
            last_high < previous_high
            and last_low < previous_low
        ):

            trend = "BEARISH"

            structure = "LH_LL"

            score += 50



        # BOS

        current_high = highs[-1]

        current_low = lows[-1]


        if trend == "BULLISH":

            if current_high > last_high:

                bos = True

                score += 25



        if trend == "BEARISH":

            if current_low < last_low:

                bos = True

                score += 25



        # CHOCH

        if trend == "BULLISH":

            if current_low < last_low:

                choch = True

                score -= 10



        if trend == "BEARISH":

            if current_high > last_high:

                choch = True

                score -= 10



        return MarketStructureResultV3(
            trend=trend,
            structure=structure,
            bos=bos,
            choch=choch,
            swing_high=last_high,
            swing_low=last_low,
            score=max(
                min(score,100),
                0,
            ),
        )
