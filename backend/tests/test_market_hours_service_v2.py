from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from backend.services.market_hours_service_v2 import (
    MarketHoursServiceV2,
)


CHICAGO = ZoneInfo("America/Chicago")
NEW_YORK = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def chicago_datetime(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int = 0,
) -> datetime:
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=CHICAGO,
    )


def always_open_calendar(
    symbol: str,
    timestamp: datetime,
) -> bool:
    return True


def always_closed_calendar(
    symbol: str,
    timestamp: datetime,
) -> bool:
    return False


def unknown_calendar(
    symbol: str,
    timestamp: datetime,
) -> None:
    return None


def test_regular_schedule_supports_nq():
    service = MarketHoursServiceV2()

    assert (
        service.is_regular_session_open(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
        is True
    )


def test_regular_schedule_supports_mnq():
    service = MarketHoursServiceV2()

    assert (
        service.is_regular_session_open(
            symbol="MNQ",
            timestamp=chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
        is True
    )


def test_regular_schedule_normalizes_symbol():
    service = MarketHoursServiceV2()

    assert (
        service.is_regular_session_open(
            symbol=" nq ",
            timestamp=chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
        is True
    )


def test_unknown_symbol_fails_closed():
    service = MarketHoursServiceV2(
        calendar_resolver=(
            always_open_calendar
        )
    )

    assert (
        service.is_market_open(
            symbol="ES",
            timestamp=chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
        is False
    )


def test_daily_maintenance_break_closed():
    service = MarketHoursServiceV2()

    assert (
        service.is_regular_session_open(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                8,
                18,
                16,
                30,
            ),
        )
        is False
    )


def test_reopens_after_daily_break():
    service = MarketHoursServiceV2()

    assert (
        service.is_regular_session_open(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                8,
                18,
                17,
            ),
        )
        is True
    )


def test_friday_weekly_close():
    service = MarketHoursServiceV2()

    before_close = chicago_datetime(
        2026,
        8,
        21,
        15,
        59,
    )

    at_close = chicago_datetime(
        2026,
        8,
        21,
        16,
    )

    assert (
        service.is_regular_session_open(
            symbol="NQ",
            timestamp=before_close,
        )
        is True
    )

    assert (
        service.is_regular_session_open(
            symbol="NQ",
            timestamp=at_close,
        )
        is False
    )


def test_saturday_closed():
    service = MarketHoursServiceV2()

    assert (
        service.is_regular_session_open(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                8,
                22,
                12,
            ),
        )
        is False
    )


def test_sunday_before_open_closed():
    service = MarketHoursServiceV2()

    assert (
        service.is_regular_session_open(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                8,
                23,
                16,
                59,
            ),
        )
        is False
    )


def test_sunday_opens_at_1700():
    service = MarketHoursServiceV2()

    assert (
        service.is_regular_session_open(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                8,
                23,
                17,
            ),
        )
        is True
    )


def test_timezone_conversion_new_york():
    service = MarketHoursServiceV2()

    timestamp = datetime(
        2026,
        8,
        18,
        17,
        30,
        tzinfo=NEW_YORK,
    )

    assert (
        service.is_regular_session_open(
            symbol="NQ",
            timestamp=timestamp,
        )
        is False
    )


def test_timezone_conversion_utc():
    service = MarketHoursServiceV2()

    timestamp = datetime(
        2026,
        8,
        18,
        22,
        0,
        tzinfo=UTC,
    )

    assert (
        service.is_regular_session_open(
            symbol="NQ",
            timestamp=timestamp,
        )
        is True
    )


def test_no_calendar_fails_closed():
    service = MarketHoursServiceV2()

    assert (
        service.is_market_open(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
        is False
    )


def test_unknown_calendar_fails_closed():
    service = MarketHoursServiceV2(
        calendar_resolver=unknown_calendar
    )

    assert (
        service.is_market_open(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
        is False
    )


def test_certified_open_calendar_allows():
    service = MarketHoursServiceV2(
        calendar_resolver=(
            always_open_calendar
        )
    )

    assert (
        service.is_market_open(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
        is True
    )


def test_certified_closed_calendar_blocks():
    service = MarketHoursServiceV2(
        calendar_resolver=(
            always_closed_calendar
        )
    )

    assert (
        service.is_market_open(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
        is False
    )


def test_calendar_cannot_override_regular_close():
    calls = []

    def resolver(
        symbol: str,
        timestamp: datetime,
    ) -> bool:
        calls.append(
            (
                symbol,
                timestamp,
            )
        )
        return True

    service = MarketHoursServiceV2(
        calendar_resolver=resolver
    )

    result = service.is_market_open(
        symbol="NQ",
        timestamp=chicago_datetime(
            2026,
            8,
            18,
            16,
            30,
        ),
    )

    assert result is False
    assert calls == []


def test_build_context_without_calendar():
    service = MarketHoursServiceV2()

    result = service.build_market_context(
        symbol="mnq",
        timestamp=chicago_datetime(
            2026,
            8,
            18,
            10,
        ),
    )

    assert result["symbol"] == "MNQ"
    assert result["supported_symbol"] is True
    assert (
        result["regular_session_open"]
        is True
    )
    assert (
        result["calendar_certified"]
        is False
    )
    assert result["calendar_status"] is None
    assert result["market_is_open"] is False
    assert (
        result["timezone"]
        == "America/Chicago"
    )


def test_build_context_certified_open():
    service = MarketHoursServiceV2(
        calendar_resolver=(
            always_open_calendar
        )
    )

    result = service.build_market_context(
        symbol="NQ",
        timestamp=chicago_datetime(
            2026,
            8,
            18,
            10,
        ),
    )

    assert (
        result["regular_session_open"]
        is True
    )
    assert (
        result["calendar_certified"]
        is True
    )
    assert result["calendar_status"] is True
    assert result["market_is_open"] is True


def test_build_context_certified_closed():
    service = MarketHoursServiceV2(
        calendar_resolver=(
            always_closed_calendar
        )
    )

    result = service.build_market_context(
        symbol="NQ",
        timestamp=chicago_datetime(
            2026,
            8,
            18,
            10,
        ),
    )

    assert (
        result["calendar_certified"]
        is True
    )
    assert result["calendar_status"] is False
    assert result["market_is_open"] is False


def test_rejects_naive_timestamp():
    service = MarketHoursServiceV2()

    with pytest.raises(
        ValueError,
        match="timezone",
    ):
        service.is_market_open(
            symbol="NQ",
            timestamp=datetime(
                2026,
                8,
                18,
                10,
            ),
        )


def test_rejects_invalid_timestamp_type():
    service = MarketHoursServiceV2()

    with pytest.raises(
        TypeError,
        match="timestamp",
    ):
        service.is_market_open(
            symbol="NQ",
            timestamp="2026-08-18",
        )


def test_rejects_empty_symbol():
    service = MarketHoursServiceV2()

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        service.is_market_open(
            symbol="   ",
            timestamp=chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )


def test_rejects_invalid_calendar_resolver():
    with pytest.raises(
        TypeError,
        match="calendar_resolver",
    ):
        MarketHoursServiceV2(
            calendar_resolver=object()
        )


def test_rejects_invalid_calendar_result():
    def invalid_resolver(
        symbol: str,
        timestamp: datetime,
    ):
        return "OPEN"

    service = MarketHoursServiceV2(
        calendar_resolver=invalid_resolver
    )

    with pytest.raises(
        TypeError,
        match="calendar_resolver",
    ):
        service.is_market_open(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
