from datetime import datetime
from zoneinfo import ZoneInfo

import pytest


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


def build_authority(*args, **kwargs):
    from backend.services.economic_news_authority_v2 import (
        EconomicNewsAuthorityV2,
    )

    return EconomicNewsAuthorityV2(
        *args,
        **kwargs,
    )


def test_no_certified_data_fails_closed():
    authority = build_authority()

    assert (
        authority.is_news_blocked(
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


def test_certified_high_impact_event_blocks():
    event_time = chicago_datetime(
        2026,
        8,
        18,
        10,
    )

    authority = build_authority(
        high_impact_events=(
            event_time,
        )
    )

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=event_time,
        )
        is True
    )


def test_certified_clear_time_does_not_block():
    event_time = chicago_datetime(
        2026,
        8,
        18,
        10,
    )

    clear_time = chicago_datetime(
        2026,
        8,
        18,
        12,
    )

    authority = build_authority(
        high_impact_events=(
            event_time,
        )
    )

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=clear_time,
        )
        is False
    )


def test_supports_mnq():
    event_time = chicago_datetime(
        2026,
        8,
        18,
        10,
    )

    authority = build_authority(
        high_impact_events=(
            event_time,
        )
    )

    assert (
        authority.is_news_blocked(
            symbol="MNQ",
            timestamp=event_time,
        )
        is True
    )


def test_normalizes_symbol():
    event_time = chicago_datetime(
        2026,
        8,
        18,
        10,
    )

    authority = build_authority(
        high_impact_events=(
            event_time,
        )
    )

    assert (
        authority.is_news_blocked(
            symbol=" nq ",
            timestamp=event_time,
        )
        is True
    )


def test_unknown_symbol_fails_closed():
    authority = build_authority(
        high_impact_events=(),
    )

    assert (
        authority.is_news_blocked(
            symbol="ES",
            timestamp=chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
        is True
    )


def test_timezone_conversion_new_york():
    chicago_event = chicago_datetime(
        2026,
        8,
        18,
        10,
    )

    authority = build_authority(
        high_impact_events=(
            chicago_event,
        )
    )

    timestamp = datetime(
        2026,
        8,
        18,
        11,
        0,
        tzinfo=NEW_YORK,
    )

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=timestamp,
        )
        is True
    )


def test_timezone_conversion_utc():
    chicago_event = chicago_datetime(
        2026,
        8,
        18,
        10,
    )

    authority = build_authority(
        high_impact_events=(
            chicago_event,
        )
    )

    timestamp = datetime(
        2026,
        8,
        18,
        15,
        0,
        tzinfo=UTC,
    )

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=timestamp,
        )
        is True
    )


def test_rejects_naive_timestamp():
    authority = build_authority()

    with pytest.raises(
        ValueError,
        match="timezone",
    ):
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=datetime(
                2026,
                8,
                18,
                10,
            ),
        )


def test_rejects_invalid_timestamp_type():
    authority = build_authority()

    with pytest.raises(
        TypeError,
        match="timestamp",
    ):
        authority.is_news_blocked(
            symbol="NQ",
            timestamp="2026-08-18T10:00:00",
        )
