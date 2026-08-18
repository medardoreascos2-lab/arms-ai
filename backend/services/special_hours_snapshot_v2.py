from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import time
from zoneinfo import ZoneInfo


@dataclass(
    frozen=True,
    slots=True,
)
class CertifiedSpecialHoursWindowV2:
    """
    Immutable certified special-hours window.

    local_date:
        Chicago calendar date explicitly certified.

    open_time / close_time:
        Certified open interval in Chicago time.

    The interval uses:
        open_time <= timestamp < close_time
    """

    local_date: date
    open_time: time
    close_time: time

    def __post_init__(self) -> None:
        if not isinstance(self.local_date, date):
            raise TypeError(
                "local_date debe ser date."
            )

        if not isinstance(self.open_time, time):
            raise TypeError(
                "open_time debe ser time."
            )

        if not isinstance(self.close_time, time):
            raise TypeError(
                "close_time debe ser time."
            )

        if (
            self.open_time.tzinfo is not None
            or self.close_time.tzinfo is not None
        ):
            raise ValueError(
                "open_time y close_time deben ser "
                "horas locales sin timezone."
            )

        if self.open_time >= self.close_time:
            raise ValueError(
                "open_time debe ser menor que close_time."
            )


@dataclass(
    frozen=True,
    slots=True,
)
class CertifiedSpecialHoursSnapshotV2:
    """
    Immutable collection of certified special-hours
    windows.

    A date absent from windows is not implicitly
    certified and therefore resolves to None.
    """

    windows: tuple[CertifiedSpecialHoursWindowV2, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.windows, tuple):
            raise TypeError(
                "windows debe ser tuple."
            )

        if not all(
            isinstance(
                value,
                CertifiedSpecialHoursWindowV2,
            )
            for value in self.windows
        ):
            raise TypeError(
                "windows debe contener "
                "CertifiedSpecialHoursWindowV2."
            )

        dates = [
            value.local_date
            for value in self.windows
        ]

        if len(dates) != len(set(dates)):
            raise ValueError(
                "No puede existir más de una ventana "
                "por fecha."
            )


class SpecialHoursResolverV2:
    """
    Fail-closed resolver for explicitly certified
    special-hours dates.

    Contract:
        True:
            timestamp is inside a certified window.

        False:
            date is certified but timestamp is
            outside its certified window.

        None:
            unsupported symbol, no snapshot, or
            date has no certified special-hours
            window.

    This component does not contain implicit holiday
    assumptions and does not replace the regular
    weekly market-hours schedule.
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
        snapshot: CertifiedSpecialHoursSnapshotV2 | None = None,
    ) -> None:
        if (
            snapshot is not None
            and not isinstance(
                snapshot,
                CertifiedSpecialHoursSnapshotV2,
            )
        ):
            raise TypeError(
                "snapshot debe ser "
                "CertifiedSpecialHoursSnapshotV2 "
                "o None."
            )

        self.snapshot = snapshot

    def resolve(
        self,
        *,
        symbol: str,
        timestamp: datetime,
    ) -> bool | None:
        normalized_symbol = self._normalize_symbol(
            symbol
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

        window = self._find_window(
            local_date
        )

        if window is None:
            return None

        local_time = (
            chicago_time.time().replace(
                tzinfo=None
            )
        )

        return bool(
            window.open_time
            <= local_time
            < window.close_time
        )

    def build_special_hours_context(
        self,
        *,
        symbol: str,
        timestamp: datetime,
    ) -> dict[str, object]:
        normalized_symbol = self._normalize_symbol(
            symbol
        )

        chicago_time = self._to_chicago_time(
            timestamp
        )

        supported = (
            normalized_symbol
            in self.SUPPORTED_SYMBOLS
        )

        local_date = chicago_time.date()

        window = (
            self._find_window(local_date)
            if supported
            and self.snapshot is not None
            else None
        )

        status = self.resolve(
            symbol=normalized_symbol,
            timestamp=timestamp,
        )

        return {
            "symbol": normalized_symbol,
            "supported_symbol": supported,
            "special_hours_date": (
                local_date.isoformat()
            ),
            "special_hours_certified": (
                window is not None
            ),
            "special_hours_status": status,
            "special_hours_open": (
                status is True
            ),
            "special_open_time": (
                window.open_time.isoformat()
                if window is not None
                else None
            ),
            "special_close_time": (
                window.close_time.isoformat()
                if window is not None
                else None
            ),
            "timezone": "America/Chicago",
            "evaluated_at": (
                chicago_time.isoformat()
            ),
        }

    def _find_window(
        self,
        local_date: date,
    ) -> CertifiedSpecialHoursWindowV2 | None:
        if self.snapshot is None:
            return None

        for window in self.snapshot.windows:
            if window.local_date == local_date:
                return window

        return None

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        if not isinstance(symbol, str):
            raise TypeError(
                "symbol debe ser str."
            )

        normalized = symbol.strip().upper()

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
        if not isinstance(timestamp, datetime):
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
