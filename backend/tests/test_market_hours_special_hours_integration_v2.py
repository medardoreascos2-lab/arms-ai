from datetime import date
from datetime import datetime
from datetime import time
from zoneinfo import ZoneInfo

import pytest

from backend.services.market_hours_service_v2 import (
    MarketHoursServiceV2,
)
from backend.services.special_hours_snapshot_v2 import (
    CertifiedSpecialHoursSnapshotV2,
    CertifiedSpecialHoursWindowV2,
    SpecialHoursResolverV2,
)


CHICAGO = ZoneInfo("America/Chicago")


SPECIAL_DATE = date(2026, 11, 27)


def timestamp(
    hour: int,
    minute: int = 0,
) -> datetime:
    return datetime(
        2026,
        11,
        27,
        hour,
        minute,
        tzinfo=CHICAGO,
    )


def certified_open_calendar(
    symbol: str,
    timestamp: datetime,
) -> bool | None:
    return True


def certified_closed_calendar(
    symbol: str,
    timestamp: datetime,
) -> bool | None:
    return False


def unknown_calendar(
    symbol: str,
    timestamp: datetime,
) -> bool | None:
    return None


def build_special_resolver() -> SpecialHoursResolverV2:
    return SpecialHoursResolverV2(
        snapshot=CertifiedSpecialHoursSnapshotV2(
            windows=(
                CertifiedSpecialHoursWindowV2(
                    local_date=SPECIAL_DATE,
                    open_time=time(8, 30),
                    close_time=time(12, 15),
                ),
            ),
        ),
    )


def test_special_hours_contract_inside_window():
    resolver = build_special_resolver()

    assert resolver.resolve(
        symbol="NQ",
        timestamp=timestamp(10, 0),
    ) is True


def test_special_hours_contract_outside_window():
    resolver = build_special_resolver()

    assert resolver.resolve(
        symbol="NQ",
        timestamp=timestamp(13, 0),
    ) is False


def test_special_hours_contract_unknown_without_snapshot():
    resolver = SpecialHoursResolverV2()

    assert resolver.resolve(
        symbol="NQ",
        timestamp=timestamp(10, 0),
    ) is None


def test_special_hours_can_restrict_certified_open_date():
    special = build_special_resolver()

    service = MarketHoursServiceV2(
        calendar_resolver=certified_open_calendar,
        special_hours_resolver=special.resolve,
    )

    assert service.is_market_open(
        symbol="NQ",
        timestamp=timestamp(13, 0),
    ) is False


def test_inside_special_window_allows_when_regular_and_calendar_allow():
    special = build_special_resolver()

    service = MarketHoursServiceV2(
        calendar_resolver=certified_open_calendar,
        special_hours_resolver=special.resolve,
    )

    assert service.is_market_open(
        symbol="NQ",
        timestamp=timestamp(10, 0),
    ) is True


def test_calendar_closed_cannot_be_reopened_by_special_hours():
    special = build_special_resolver()

    service = MarketHoursServiceV2(
        calendar_resolver=certified_closed_calendar,
        special_hours_resolver=special.resolve,
    )

    assert service.is_market_open(
        symbol="NQ",
        timestamp=timestamp(10, 0),
    ) is False


def test_unknown_calendar_remains_fail_closed():
    special = build_special_resolver()

    service = MarketHoursServiceV2(
        calendar_resolver=unknown_calendar,
        special_hours_resolver=special.resolve,
    )

    assert service.is_market_open(
        symbol="NQ",
        timestamp=timestamp(10, 0),
    ) is False
