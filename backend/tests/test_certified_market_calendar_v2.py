from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from backend.services.certified_market_calendar_v2 import (
    CertifiedCalendarSnapshotV2,
)
from backend.services.certified_market_calendar_v2 import (
    CertifiedMarketCalendarV2,
)
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


def build_snapshot():
    return CertifiedCalendarSnapshotV2(
        covered_dates=frozenset(
            {
                date(2026, 1, 1),
                date(2026, 8, 18),
                date(2026, 12, 25),
            }
        ),
        closed_dates=frozenset(
            {
                date(2026, 1, 1),
                date(2026, 12, 25),
            }
        ),
    )


def test_snapshot_is_immutable():
    snapshot = build_snapshot()

    with pytest.raises(
        AttributeError,
    ):
        snapshot.covered_dates = frozenset()


def test_rejects_non_frozenset_coverage():
    with pytest.raises(
        TypeError,
        match="covered_dates",
    ):
        CertifiedCalendarSnapshotV2(
            covered_dates={
                date(2026, 8, 18),
            },
            closed_dates=frozenset(),
        )


def test_rejects_non_frozenset_closed_dates():
    with pytest.raises(
        TypeError,
        match="closed_dates",
    ):
        CertifiedCalendarSnapshotV2(
            covered_dates=frozenset(
                {
                    date(2026, 8, 18),
                }
            ),
            closed_dates={
                date(2026, 8, 18),
            },
        )


def test_closed_dates_must_be_covered():
    with pytest.raises(
        ValueError,
        match="subconjunto",
    ):
        CertifiedCalendarSnapshotV2(
            covered_dates=frozenset(
                {
                    date(2026, 8, 18),
                }
            ),
            closed_dates=frozenset(
                {
                    date(2026, 12, 25),
                }
            ),
        )


def test_no_snapshot_returns_none():
    calendar = CertifiedMarketCalendarV2()

    assert (
        calendar(
            "NQ",
            chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
        is None
    )


def test_covered_open_date_returns_true():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    assert (
        calendar(
            "NQ",
            chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
        is True
    )


def test_covered_closed_date_returns_false():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    assert (
        calendar(
            "NQ",
            chicago_datetime(
                2026,
                12,
                25,
                10,
            ),
        )
        is False
    )


def test_uncovered_date_returns_none():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    assert (
        calendar(
            "NQ",
            chicago_datetime(
                2026,
                8,
                19,
                10,
            ),
        )
        is None
    )


def test_unknown_year_returns_none():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    assert (
        calendar(
            "NQ",
            chicago_datetime(
                2027,
                8,
                18,
                10,
            ),
        )
        is None
    )


def test_supports_mnq():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    assert (
        calendar(
            "MNQ",
            chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
        is True
    )


def test_normalizes_symbol():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    assert (
        calendar(
            " nq ",
            chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
        is True
    )


def test_unknown_symbol_returns_none():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    assert (
        calendar(
            "ES",
            chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
        is None
    )


def test_timezone_conversion_new_york():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    timestamp = datetime(
        2026,
        8,
        18,
        11,
        0,
        tzinfo=NEW_YORK,
    )

    assert calendar("NQ", timestamp) is True


def test_timezone_conversion_utc():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    timestamp = datetime(
        2026,
        8,
        18,
        15,
        0,
        tzinfo=UTC,
    )

    assert calendar("NQ", timestamp) is True


def test_rejects_naive_timestamp():
    calendar = CertifiedMarketCalendarV2()

    with pytest.raises(
        ValueError,
        match="timezone",
    ):
        calendar(
            "NQ",
            datetime(
                2026,
                8,
                18,
                10,
            ),
        )


def test_rejects_invalid_timestamp_type():
    calendar = CertifiedMarketCalendarV2()

    with pytest.raises(
        TypeError,
        match="timestamp",
    ):
        calendar(
            "NQ",
            "2026-08-18",
        )


def test_rejects_empty_symbol():
    calendar = CertifiedMarketCalendarV2()

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        calendar(
            "   ",
            chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )


def test_rejects_invalid_snapshot():
    with pytest.raises(
        TypeError,
        match="snapshot",
    ):
        CertifiedMarketCalendarV2(
            snapshot=object()
        )


def test_build_calendar_context_open():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    context = (
        calendar.build_calendar_context(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                8,
                18,
                10,
            ),
        )
    )

    assert (
        context["calendar_certified"]
        is True
    )

    assert (
        context["calendar_status"]
        is True
    )

    assert (
        context["market_calendar_open"]
        is True
    )


def test_build_calendar_context_unknown():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    context = (
        calendar.build_calendar_context(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                8,
                19,
                10,
            ),
        )
    )

    assert (
        context["calendar_certified"]
        is False
    )

    assert (
        context["calendar_status"]
        is None
    )

    assert (
        context["market_calendar_open"]
        is False
    )


def test_integrates_open_with_market_hours():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    service = MarketHoursServiceV2(
        calendar_resolver=calendar
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


def test_uncovered_date_blocks_market_hours():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    service = MarketHoursServiceV2(
        calendar_resolver=calendar
    )

    assert (
        service.is_market_open(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                8,
                19,
                10,
            ),
        )
        is False
    )


def test_closed_date_blocks_market_hours():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    service = MarketHoursServiceV2(
        calendar_resolver=calendar
    )

    assert (
        service.is_market_open(
            symbol="NQ",
            timestamp=chicago_datetime(
                2026,
                12,
                25,
                10,
            ),
        )
        is False
    )


def test_regular_schedule_still_has_priority():
    calendar = CertifiedMarketCalendarV2(
        snapshot=build_snapshot()
    )

    service = MarketHoursServiceV2(
        calendar_resolver=calendar
    )

    assert (
        service.is_market_open(
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


def test_snapshot_reports_explicitly_covered_date():
    snapshot = CertifiedCalendarSnapshotV2(
        covered_dates=frozenset(
            {
                date(2026, 8, 18),
                date(2026, 8, 20),
            }
        ),
        closed_dates=frozenset(),
    )

    assert (
        snapshot.is_date_covered(
            target_date=date(2026, 8, 18),
        )
        is True
    )


def test_snapshot_reports_uncovered_gap_date():
    snapshot = CertifiedCalendarSnapshotV2(
        covered_dates=frozenset(
            {
                date(2026, 8, 18),
                date(2026, 8, 20),
            }
        ),
        closed_dates=frozenset(),
    )

    assert (
        snapshot.is_date_covered(
            target_date=date(2026, 8, 19),
        )
        is False
    )


def test_snapshot_reports_date_outside_coverage():
    snapshot = CertifiedCalendarSnapshotV2(
        covered_dates=frozenset(
            {
                date(2026, 8, 18),
            }
        ),
        closed_dates=frozenset(),
    )

    assert (
        snapshot.is_date_covered(
            target_date=date(2026, 8, 20),
        )
        is False
    )


def test_snapshot_coverage_query_rejects_non_date():
    snapshot = CertifiedCalendarSnapshotV2(
        covered_dates=frozenset(
            {
                date(2026, 8, 18),
            }
        ),
        closed_dates=frozenset(),
    )

    with pytest.raises(
        TypeError,
        match="target_date",
    ):
        snapshot.is_date_covered(
            target_date="2026-08-18",
        )
