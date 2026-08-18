from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time
from zoneinfo import ZoneInfo


CalendarResolver = Callable[
    [str, datetime],
    bool | None,
]


SpecialHoursResolver = Callable[
    ...,
    bool | None,
]


class MarketHoursServiceV2:
    """
    Fail-closed market-hours gate for supported
    CME equity index futures.

    The weekly schedule determines whether a
    timestamp belongs to the normal electronic
    trading session.

    Actual market-open status additionally requires
    a certified calendar resolver.

    Resolver contract:
        True:
            certified open
        False:
            certified closed
        None:
            calendar status unknown

    Unknown calendar status always fails closed.
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

    DAILY_BREAK_START = time(16, 0)
    DAILY_BREAK_END = time(17, 0)

    WEEKLY_OPEN = time(17, 0)
    WEEKLY_CLOSE = time(16, 0)

    def __init__(
        self,
        *,
        calendar_resolver: (
            CalendarResolver | None
        ) = None,
        special_hours_resolver: (
            SpecialHoursResolver | None
        ) = None,
    ) -> None:
        if (
            calendar_resolver is not None
            and not callable(
                calendar_resolver
            )
        ):
            raise TypeError(
                "calendar_resolver debe ser "
                "callable o None."
            )

        self.calendar_resolver = (
            calendar_resolver
        )

        if (
            special_hours_resolver is not None
            and not callable(
                special_hours_resolver
            )
        ):
            raise TypeError(
                "special_hours_resolver debe ser "
                "callable o None."
            )

        self.special_hours_resolver = (
            special_hours_resolver
        )

    def is_regular_session_open(
        self,
        *,
        symbol: str,
        timestamp: datetime,
    ) -> bool:
        normalized_symbol = (
            self._normalize_symbol(
                symbol
            )
        )

        if (
            normalized_symbol
            not in self.SUPPORTED_SYMBOLS
        ):
            return False

        chicago_time = self._to_chicago_time(
            timestamp
        )

        weekday = chicago_time.weekday()

        local_time = (
            chicago_time.time().replace(
                tzinfo=None
            )
        )

        # Saturday: closed all day.
        if weekday == 5:
            return False

        # Sunday: weekly open at 17:00 CT.
        if weekday == 6:
            return (
                local_time
                >= self.WEEKLY_OPEN
            )

        # Friday: weekly close at 16:00 CT.
        if weekday == 4:
            return (
                local_time
                < self.WEEKLY_CLOSE
            )

        # Monday through Thursday:
        # 16:00-17:00 CT maintenance break.
        if (
            self.DAILY_BREAK_START
            <= local_time
            < self.DAILY_BREAK_END
        ):
            return False

        return True

    def is_market_open(
        self,
        *,
        symbol: str,
        timestamp: datetime,
    ) -> bool:
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
            return False

        if not self.is_regular_session_open(
            symbol=normalized_symbol,
            timestamp=timestamp,
        ):
            return False

        if self.calendar_resolver is None:
            return False

        calendar_status = (
            self.calendar_resolver(
                normalized_symbol,
                chicago_time,
            )
        )

        if calendar_status is None:
            return False

        if not isinstance(
            calendar_status,
            bool,
        ):
            raise TypeError(
                "calendar_resolver debe "
                "retornar bool o None."
            )

        if self.special_hours_resolver is not None:
            special_hours_status = (
                self.special_hours_resolver(
                    symbol=normalized_symbol,
                    timestamp=timestamp,
                )
            )

            if (
                special_hours_status is not None
                and not isinstance(
                    special_hours_status,
                    bool,
                )
            ):
                raise TypeError(
                    "special_hours_resolver debe "
                    "retornar bool o None."
                )

            if special_hours_status is False:
                return False

        return calendar_status

    def build_market_context(
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

        regular_session_open = (
            supported
            and self.is_regular_session_open(
                symbol=normalized_symbol,
                timestamp=timestamp,
            )
        )

        calendar_status: bool | None = None

        if (
            supported
            and regular_session_open
            and self.calendar_resolver
            is not None
        ):
            calendar_status = (
                self.calendar_resolver(
                    normalized_symbol,
                    chicago_time,
                )
            )

            if (
                calendar_status is not None
                and not isinstance(
                    calendar_status,
                    bool,
                )
            ):
                raise TypeError(
                    "calendar_resolver debe "
                    "retornar bool o None."
                )

        special_hours_status: bool | None = None

        if self.special_hours_resolver is not None:
            special_hours_status = (
                self.special_hours_resolver(
                    symbol=normalized_symbol,
                    timestamp=timestamp,
                )
            )

            if (
                special_hours_status is not None
                and not isinstance(
                    special_hours_status,
                    bool,
                )
            ):
                raise TypeError(
                    "special_hours_resolver debe "
                    "retornar bool o None."
                )

        special_hours_allows = (
            special_hours_status is not False
        )

        market_is_open = bool(
            regular_session_open
            and calendar_status is True
            and special_hours_allows
        )

        return {
            "symbol": normalized_symbol,
            "supported_symbol": supported,
            "regular_session_open": (
                regular_session_open
            ),
            "calendar_certified": (
                calendar_status
                is not None
            ),
            "calendar_status": (
                calendar_status
            ),
            "market_is_open": (
                market_is_open
            ),
            "timezone": (
                "America/Chicago"
            ),
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
