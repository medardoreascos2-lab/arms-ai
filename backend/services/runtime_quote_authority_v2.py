from __future__ import annotations

from datetime import datetime
from math import isfinite
from threading import RLock
from typing import TypedDict


class RuntimeQuoteV2(TypedDict):
    symbol: str
    bid: float
    ask: float
    timestamp: datetime


class RuntimeQuoteAuthorityV2:
    """
    In-memory runtime authority for certified L1 bid/ask quotes.

    This component stores only explicitly supplied bid/ask quotes.

    It does not:
    - infer quotes from OHLC candles,
    - infer spread from ATR,
    - infer spread from last price,
    - manufacture a synthetic spread.
    """

    def __init__(self) -> None:
        self._quotes: dict[str, RuntimeQuoteV2] = {}
        self._lock = RLock()

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        if not isinstance(symbol, str):
            raise ValueError(
                "symbol must be a non-empty string"
            )

        normalized = symbol.strip().upper()

        if not normalized:
            raise ValueError(
                "symbol must be a non-empty string"
            )

        return normalized

    @staticmethod
    def _normalize_price(
        value: float,
        *,
        field_name: str,
    ) -> float:
        try:
            normalized = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{field_name} must be a finite positive number"
            ) from exc

        if (
            not isfinite(normalized)
            or normalized <= 0.0
        ):
            raise ValueError(
                f"{field_name} must be a finite positive number"
            )

        return normalized

    @staticmethod
    def _validate_timestamp(
        timestamp: datetime,
    ) -> datetime:
        if not isinstance(timestamp, datetime):
            raise ValueError(
                "timestamp must be a timezone-aware datetime"
            )

        if (
            timestamp.tzinfo is None
            or timestamp.utcoffset() is None
        ):
            raise ValueError(
                "timestamp must be a timezone-aware datetime"
            )

        return timestamp

    def publish_quote(
        self,
        *,
        symbol: str,
        bid: float,
        ask: float,
        timestamp: datetime,
    ) -> None:
        normalized_symbol = self._normalize_symbol(
            symbol
        )
        normalized_bid = self._normalize_price(
            bid,
            field_name="bid",
        )
        normalized_ask = self._normalize_price(
            ask,
            field_name="ask",
        )
        normalized_timestamp = self._validate_timestamp(
            timestamp
        )

        if normalized_ask < normalized_bid:
            raise ValueError(
                "ask must be greater than or equal to bid"
            )

        quote: RuntimeQuoteV2 = {
            "symbol": normalized_symbol,
            "bid": normalized_bid,
            "ask": normalized_ask,
            "timestamp": normalized_timestamp,
        }

        with self._lock:
            current = self._quotes.get(
                normalized_symbol
            )

            if (
                current is not None
                and normalized_timestamp
                < current["timestamp"]
            ):
                raise ValueError(
                    "quote timestamp cannot move backwards"
                )

            self._quotes[normalized_symbol] = quote

    def get_quote(
        self,
        *,
        symbol: str,
    ) -> RuntimeQuoteV2 | None:
        normalized_symbol = self._normalize_symbol(
            symbol
        )

        with self._lock:
            quote = self._quotes.get(
                normalized_symbol
            )

            if quote is None:
                return None

            return {
                "symbol": quote["symbol"],
                "bid": quote["bid"],
                "ask": quote["ask"],
                "timestamp": quote["timestamp"],
            }
