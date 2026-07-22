from __future__ import annotations

from collections import defaultdict

from backend.models.candle import Candle


class LiveCandleStore:
    """
    Almacena velas en memoria por símbolo y temporalidad.

    Cada mercado se identifica mediante:
        (symbol, timeframe)
    """

    def __init__(
        self,
        max_candles: int = 500,
    ) -> None:
        if max_candles <= 0:
            raise ValueError(
                "max_candles debe ser mayor que cero."
            )

        self.max_candles = max_candles

        self._candles: dict[
            tuple[str, str],
            dict[object, Candle],
        ] = defaultdict(dict)

    def add(
        self,
        candle: Candle,
    ) -> None:
        if not isinstance(
            candle,
            Candle,
        ):
            raise TypeError(
                "candle debe ser una instancia de Candle."
            )

        key = (
            candle.symbol,
            candle.timeframe,
        )

        market_candles = self._candles[key]

        # El timestamp funciona como identificador único.
        # Si ya existe, reemplazamos la vela.
        market_candles[
            candle.timestamp
        ] = candle

        if (
            len(market_candles)
            > self.max_candles
        ):
            ordered_timestamps = sorted(
                market_candles
            )

            excess = (
                len(market_candles)
                - self.max_candles
            )

            for timestamp in (
                ordered_timestamps[:excess]
            ):
                del market_candles[
                    timestamp
                ]

    def get_latest(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[Candle]:
        if limit <= 0:
            raise ValueError(
                "limit debe ser mayor que cero."
            )

        normalized_symbol = (
            str(symbol)
            .strip()
        )

        normalized_timeframe = (
            str(timeframe)
            .strip()
        )

        if not normalized_symbol:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        if not normalized_timeframe:
            raise ValueError(
                "timeframe no puede estar vacío."
            )

        key = (
            normalized_symbol,
            normalized_timeframe,
        )

        market_candles = self._candles.get(
            key,
            {},
        )

        ordered = sorted(
            market_candles.values(),
            key=lambda candle: (
                candle.timestamp
            ),
        )

        return ordered[-limit:]

    def count(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> int:
        key = (
            str(symbol).strip(),
            str(timeframe).strip(),
        )

        return len(
            self._candles.get(
                key,
                {},
            )
        )

    def clear(
        self,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> None:
        if (
            symbol is None
            and timeframe is None
        ):
            self._candles.clear()
            return

        if (
            symbol is None
            or timeframe is None
        ):
            raise ValueError(
                "symbol y timeframe deben proporcionarse juntos."
            )

        key = (
            str(symbol).strip(),
            str(timeframe).strip(),
        )

        self._candles.pop(
            key,
            None,
        )
