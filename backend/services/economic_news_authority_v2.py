from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from zoneinfo import ZoneInfo


CHICAGO = ZoneInfo("America/Chicago")

_SUPPORTED_SYMBOLS = frozenset(
    {
        "NQ",
        "MNQ",
    }
)


class EconomicNewsAuthorityV2:
    """
    Minimal fail-closed authority for certified
    high-impact economic-news timestamps.

    This component intentionally does not fetch,
    discover, or infer economic events.

    It only evaluates explicitly supplied certified
    high-impact event timestamps.

    A separate runtime data provider/lifecycle layer
    may populate certified events later.
    """

    def __init__(
        self,
        *,
        high_impact_events: Iterable[datetime] | None = None,
    ) -> None:
        self._has_certified_data = (
            high_impact_events is not None
        )

        if high_impact_events is None:
            self._high_impact_events = frozenset()
            return

        normalized_events: set[datetime] = set()

        for event in high_impact_events:
            self._validate_timestamp(event)

            normalized_events.add(
                event.astimezone(CHICAGO)
            )

        self._high_impact_events = frozenset(
            normalized_events
        )

    def is_news_blocked(
        self,
        *,
        symbol: str,
        timestamp: datetime,
    ) -> bool:
        self._validate_timestamp(timestamp)

        normalized_symbol = str(symbol).strip().upper()

        if normalized_symbol not in _SUPPORTED_SYMBOLS:
            return True

        if not self._has_certified_data:
            return True

        normalized_timestamp = timestamp.astimezone(
            CHICAGO
        )

        return (
            normalized_timestamp
            in self._high_impact_events
        )

    @staticmethod
    def _validate_timestamp(
        timestamp: datetime,
    ) -> None:
        if not isinstance(timestamp, datetime):
            raise TypeError(
                "timestamp must be a datetime"
            )

        if (
            timestamp.tzinfo is None
            or timestamp.utcoffset() is None
        ):
            raise ValueError(
                "timestamp must include timezone information"
            )
