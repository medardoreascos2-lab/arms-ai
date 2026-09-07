from __future__ import annotations

from datetime import datetime
from math import isfinite

from backend.services.runtime_quote_authority_v2 import (
    RuntimeQuoteAuthorityV2,
)
from backend.services.spread_authority_v2 import (
    SpreadAuthorityV2,
)


class RuntimeSpreadAuthorityV2:
    """
    Resolve current spread from a symbol-scoped runtime L1 quote.

    The authority is intentionally fail-closed.

    It does not:
    - infer spread from OHLC candles,
    - infer spread from ATR,
    - infer spread from last price,
    - use tick size as spread,
    - manufacture a static fallback spread.
    """

    def __init__(
        self,
        *,
        quote_authority: RuntimeQuoteAuthorityV2,
        spread_authority: SpreadAuthorityV2,
        maximum_quote_age_seconds: float,
    ) -> None:
        maximum_age = float(
            maximum_quote_age_seconds
        )

        if (
            not isfinite(maximum_age)
            or maximum_age <= 0.0
        ):
            raise ValueError(
                "maximum_quote_age_seconds "
                "must be a finite positive number"
            )

        self._quote_authority = quote_authority
        self._spread_authority = spread_authority
        self._maximum_quote_age_seconds = maximum_age

    @staticmethod
    def _validate_now(
        now: datetime,
    ) -> datetime:
        if not isinstance(now, datetime):
            raise ValueError(
                "now must be a timezone-aware datetime"
            )

        if (
            now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise ValueError(
                "now must be a timezone-aware datetime"
            )

        return now

    def get_spread_points(
        self,
        *,
        symbol: str,
        now: datetime,
    ) -> float:
        normalized_now = self._validate_now(now)

        quote = self._quote_authority.get_quote(
            symbol=symbol,
        )

        if quote is None:
            raise RuntimeError(
                "runtime quote is unavailable"
            )

        quote_timestamp = quote["timestamp"]

        age_seconds = (
            normalized_now - quote_timestamp
        ).total_seconds()

        if age_seconds < 0.0:
            raise RuntimeError(
                "runtime quote timestamp is in the future"
            )

        if (
            age_seconds
            > self._maximum_quote_age_seconds
        ):
            raise RuntimeError(
                "runtime quote is stale"
            )

        return self._spread_authority.resolve_spread_points(
            symbol=quote["symbol"],
            bid=quote["bid"],
            ask=quote["ask"],
        )
