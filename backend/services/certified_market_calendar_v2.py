from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass(
    frozen=True,
    slots=True,
)
class CertifiedCalendarSnapshotV2:
    """
    Immutable certified calendar snapshot.

    covered_dates:
        Dates whose holiday/special-hours status
        has been explicitly certified.

    closed_dates:
        Certified dates on which the market must
        remain closed for the entire regular
        session.

    A date absent from covered_dates is UNKNOWN.
    """

    covered_dates: frozenset[date]
    closed_dates: frozenset[date]

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.covered_dates,
            frozenset,
        ):
            raise TypeError(
                "covered_dates debe ser frozenset."
            )

        if not isinstance(
            self.closed_dates,
            frozenset,
        ):
            raise TypeError(
                "closed_dates debe ser frozenset."
            )

        if not all(
            isinstance(value, date)
            for value
            in self.covered_dates
        ):
            raise TypeError(
                "covered_dates debe contener date."
            )

        if not all(
            isinstance(value, date)
            for value
            in self.closed_dates
        ):
            raise TypeError(
                "closed_dates debe contener date."
            )

        if not self.closed_dates.issubset(
            self.covered_dates
        ):
            raise ValueError(
                "closed_dates debe ser subconjunto "
                "de covered_dates."
            )


class CertifiedMarketCalendarV2:
    """
    Fail-closed certified calendar resolver.

    The service contains no implicit holiday
    assumptions.

    Only dates contained in a supplied immutable
    certified snapshot may return True or False.

    Resolver contract:
        True:
            covered date certified open
        False:
            covered date certified closed
        None:
            unsupported symbol or date not covered

    MarketHoursServiceV2 remains responsible for
    the regular weekly trading schedule.
    """

    CHICAGO_TIMEZONE = ZoneInfo(
        "America/Chicago"
    )

    SUPPORTED_SYMBOLS = frozenset(
        {
            "NQ",
            "MNQ",
        }
    )

    def __init__(
        self,
        *,
        snapshot: (
            CertifiedCalendarSnapshotV2 | None
        ) = None,
    ) -> None:
        if (
            snapshot is not None
            and not isinstance(
                snapshot,
                CertifiedCalendarSnapshotV2,
            )
        ):
            raise TypeError(
                "snapshot debe ser "
                "CertifiedCalendarSnapshotV2 "
                "o None."
            )

        self.snapshot = snapshot

    def __call__(
        self,
        symbol: str,
        timestamp: datetime,
    ) -> bool | None:
        return self.resolve(
            symbol=symbol,
            timestamp=timestamp,
        )

    def resolve(
        self,
        *,
        symbol: str,
        timestamp: datetime,
    ) -> bool | None:
        normalized_symbol = (
            self._normalize_symbol(
                symbol
            )
        )

        chicago_time = self._to_chicago_time(
            timestamp
        )

        if (
            normalized_symbol
            not in self.SUPPORTED_SYMBOLS
        ):
            return None

        if self.snapshot is None:
            return None

        local_date = chicago_time.date()

        if (
            local_date
            not in self.snapshot.covered_dates
        ):
            return None

        if (
            local_date
            in self.snapshot.closed_dates
        ):
            return False

        return True

    def build_calendar_context(
        self,
        *,
        symbol: str,
        timestamp: datetime,
    ) -> dict[str, object]:
        normalized_symbol = (
            self._normalize_symbol(
                symbol
            )
        )

        chicago_time = self._to_chicago_time(
            timestamp
        )

        supported = (
            normalized_symbol
            in self.SUPPORTED_SYMBOLS
        )

        local_date = chicago_time.date()

        covered = bool(
            supported
            and self.snapshot is not None
            and local_date
            in self.snapshot.covered_dates
        )

        status = self.resolve(
            symbol=normalized_symbol,
            timestamp=timestamp,
        )

        return {
            "symbol": normalized_symbol,
            "supported_symbol": supported,
            "calendar_date": (
                local_date.isoformat()
            ),
            "calendar_certified": covered,
            "calendar_status": status,
            "market_calendar_open": (
                status is True
            ),
            "timezone": "America/Chicago",
            "evaluated_at": (
                chicago_time.isoformat()
            ),
        }

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        if not isinstance(symbol, str):
            raise TypeError(
                "symbol debe ser str."
            )

        normalized = (
            symbol.strip().upper()
        )

        if not normalized:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        return normalized

    @classmethod
    def _to_chicago_time(
        cls,
        timestamp: datetime,
    ) -> datetime:
        if not isinstance(
            timestamp,
            datetime,
        ):
            raise TypeError(
                "timestamp debe ser datetime."
            )

        if timestamp.tzinfo is None:
            raise ValueError(
                "timestamp debe incluir timezone."
            )

        return timestamp.astimezone(
            cls.CHICAGO_TIMEZONE
        )
