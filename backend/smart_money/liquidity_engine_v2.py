from backend.models.candle import Candle


class LiquidityEngineV2:
    """
    Motor avanzado de liquidez para ARMS AI.

    Detecta:
    - Equal highs
    - Equal lows
    - Liquidity sweep
    - Dirección del sweep
    - Nivel de liquidez
    - Índice donde ocurrió
    """

    def __init__(
        self,
        tolerance: float = 1.0,
        lookback: int = 5,
    ) -> None:

        self.tolerance = tolerance
        self.lookback = lookback

        self.equal_highs = False
        self.equal_lows = False

        self.sweep_detected = "NO"
        self.sweep_direction = "NINGUNA"

        self.liquidity_level = None
        self.sweep_index = None


    def analyze(
        self,
        candles: list[Candle],
    ) -> str:

        if len(candles) < self.lookback + 2:
            raise ValueError(
                "No hay suficientes velas para analizar liquidez."
            )


        recent = candles[-(self.lookback + 3):]


        liquidity_candles = recent[:-4]

        sweep_candle = recent[-4]


        highs = [
            candle.high
            for candle in liquidity_candles
        ]

        lows = [
            candle.low
            for candle in liquidity_candles
        ]


        high_level = max(highs)
        low_level = min(lows)


        self.equal_highs = (
            sum(
                abs(h - high_level) <= self.tolerance
                for h in highs
            )
            >= 2
        )


        self.equal_lows = (
            sum(
                abs(l - low_level) <= self.tolerance
                for l in lows
            )
            >= 2
        )


        self.sweep_detected = "NO"
        self.sweep_direction = "NINGUNA"
        self.liquidity_level = None
        self.sweep_index = None


        for index, candle in enumerate([sweep_candle]):

            # Sweep de mínimos
            if (
                self.equal_lows
                and candle.low < low_level
                and candle.close > low_level
            ):
                self.sweep_detected = "SÍ"
                self.sweep_direction = "ALCISTA"
                self.liquidity_level = low_level
                self.sweep_index = index
                break


            # Sweep de máximos
            if (
                self.equal_highs
                and candle.high > high_level
                and candle.close < high_level
            ):
                self.sweep_detected = "SÍ"
                self.sweep_direction = "BAJISTA"
                self.liquidity_level = high_level
                self.sweep_index = index
                break


        return self.sweep_detected


    def show(self):

        print("------ LIQUIDITY ENGINE V2 ------")

        print(
            "Equal Highs:",
            self.equal_highs
        )

        print(
            "Equal Lows:",
            self.equal_lows
        )

        print(
            "Sweep:",
            self.sweep_detected
        )

        print(
            "Direction:",
            self.sweep_direction
        )

        print(
            "Liquidity Level:",
            self.liquidity_level
        )

        print(
            "Sweep Index:",
            self.sweep_index
        )
