from __future__ import annotations

from collections import defaultdict
from threading import RLock

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
        # Serialize public ingestion and its derived analysis as one operation.
        self.ingestion_lock = RLock()

        self._candles: dict[
            tuple[str, str],
            dict[object, Candle],
        ] = defaultdict(dict)

    def ingest(self, candle: Candle) -> bool:
        """Append a closed application candle; replay's replacing add stays separate.

        Equal input is idempotent. Corrections and late observations require an
        explicit replay, never silently rewrite operational indicator history.
        """
        from dataclasses import replace
        from datetime import datetime, timezone
        from math import isfinite

        if not isinstance(candle, Candle):
            raise TypeError("candle must be a Candle")
        if candle.timestamp.tzinfo is None or candle.timestamp.utcoffset() is None:
            raise ValueError("candle timestamp must be timezone aware")
        if candle.timestamp > datetime.now(timezone.utc):
            raise ValueError("future candle timestamp")
        if any(not isfinite(float(v)) or float(v) <= 0 for v in
               (candle.open, candle.high, candle.low, candle.close)):
            raise ValueError("candle prices must be finite and positive")
        if not isfinite(float(candle.volume)) or candle.volume < 0:
            raise ValueError("invalid candle volume")
        if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
            raise ValueError("invalid candle OHLC")
        candle = replace(candle, symbol=candle.symbol.strip().upper(),
                         timeframe=candle.timeframe.strip().upper())
        with self.ingestion_lock:
            latest = self.get_latest(symbol=candle.symbol, timeframe=candle.timeframe,
                                     limit=self.max_candles)
            for existing in latest:
                if existing.timestamp == candle.timestamp:
                    if replace(existing, symbol=existing.symbol.upper(),
                               timeframe=existing.timeframe.upper()) == candle:
                        return False
                    raise ValueError("conflicting candle timestamp")
            if latest and candle.timestamp < latest[-1].timestamp:
                raise ValueError("out-of-order candle timestamp")
            self.add(candle)
            return True

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

        normalized_symbol = (
            str(
                candle.symbol
            )
            .strip()
            .upper()
        )

        normalized_timeframe = (
            str(
                candle.timeframe
            )
            .strip()
            .upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "candle.symbol no puede estar vacío."
            )

        if not normalized_timeframe:
            raise ValueError(
                "candle.timeframe no puede estar vacío."
            )

        key = (
            normalized_symbol,
            normalized_timeframe,
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
            .upper()
        )

        normalized_timeframe = (
            str(timeframe)
            .strip()
            .upper()
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
            str(symbol)
            .strip()
            .upper(),
            str(timeframe)
            .strip()
            .upper(),
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
            str(symbol)
            .strip()
            .upper(),
            str(timeframe)
            .strip()
            .upper(),
        )

        self._candles.pop(
            key,
            None,
        )
