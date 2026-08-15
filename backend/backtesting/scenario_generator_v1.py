from backend.models.candle import Candle


class ScenarioGeneratorV1:
    """
    Generador de escenarios sintéticos para validar
    la inteligencia de ARMS AI.
    """

    def bullish_breakout(
        self,
        symbol: str = "NQ",
        timeframe: str = "5m",
    ) -> list[Candle]:

        prices = [
            21000,
            20950,
            20900,
            20900,
            20870,
            20940,
            21020,
            21100,
        ]

        return self._build(
            prices,
            symbol,
            timeframe,
        )



    def bullish_a_plus_setup(
        self,
        symbol: str = "NQ",
        timeframe: str = "5m",
    ) -> list[Candle]:

        prices = [
            21000,
            20950,
            20900,
            20900,
            20800,
            20950,
            21000,
            21200,
        ]

        return self._build(
            prices,
            symbol,
            timeframe,
        )


    def bearish_breakout(
        self,
        symbol: str = "NQ",
        timeframe: str = "5m",
    ) -> list[Candle]:

        prices = [
            21300,
            21250,
            21200,
            21150,
            21100,
            21160,
            21200,
            21240,
            21280,
            21200,
            21120,
            21040,
            20950,
        ]

        return self._build(
            prices,
            symbol,
            timeframe,
        )





    def false_breakout_setup(
        self,
        symbol: str = "NQ",
        timeframe: str = "5m",
    ) -> list[Candle]:

        prices = [
            21000,
            21050,
            21100,
            21100,
            21150,
            21080,
            21020,
            20950,
        ]

        return self._build(
            prices,
            symbol,
            timeframe,
        )


    def no_trade_setup(
        self,
        symbol: str = "NQ",
        timeframe: str = "5m",
    ) -> list[Candle]:

        prices = [
            21000,
            21010,
            20995,
            21005,
            21000,
            21015,
            20990,
            21005,
        ]

        return self._build(
            prices,
            symbol,
            timeframe,
        )


    def bearish_a_plus_setup(
        self,
        symbol: str = "NQ",
        timeframe: str = "5m",
    ) -> list[Candle]:

        prices = [
            21200,
            21250,
            21300,
            21300,
            21400,
            21250,
            21250,
            20950,
        ]

        return self._build(
            prices,
            symbol,
            timeframe,
        )


    def sideways(
        self,
        symbol: str = "NQ",
        timeframe: str = "5m",
    ) -> list[Candle]:

        prices = [
            21000,
            21020,
            20990,
            21010,
            20980,
            21015,
            20995,
            21005,
        ] * 5

        return self._build(
            prices,
            symbol,
            timeframe,
        )


    def _build(
        self,
        prices,
        symbol,
        timeframe,
    ) -> list[Candle]:

        candles = []

        warmup_price = prices[0]

        for i in range(50):
            candles.append(
                Candle(
                    timestamp=f"2025-01-01 00:{i:02d}",
                    open=warmup_price - 5,
                    high=warmup_price + 10,
                    low=warmup_price - 10,
                    close=warmup_price,
                    volume=1000,
                    symbol=symbol,
                    timeframe=timeframe,
                )
            )

        offset = 50

        for i, price in enumerate(prices):

            if price == 20940:
                candles.append(
                    Candle(
                        timestamp=f"2025-01-01 00:{i + offset:02d}",
                        open=21010,
                        high=21080,
                        low=20940,
                        close=21020,
                        volume=1000,
                        symbol=symbol,
                        timeframe=timeframe,
                    )
                )

            elif price == 20800:
                candles.append(
                    Candle(
                        timestamp=f"2025-01-01 00:{i + offset:02d}",
                        open=20870,
                        high=20920,
                        low=20750,
                        close=20900,
                        volume=1000,
                        symbol=symbol,
                        timeframe=timeframe,
                    )
                )

            elif price == 21400:
                candles.append(
                    Candle(
                        timestamp=f"2025-01-01 00:{i + offset:02d}",
                        open=21380,
                        high=21450,
                        low=21350,
                        close=21300,
                        volume=1000,
                        symbol=symbol,
                        timeframe=timeframe,
                    )
                )

            else:
                candles.append(
                    Candle(
                        timestamp=f"2025-01-01 00:{i + offset:02d}",
                        open=price - 10,
                        high=price + 50,
                        low=price - 50,
                        close=price,
                        volume=1000,
                        symbol=symbol,
                        timeframe=timeframe,
                    )
                )

        return candles
