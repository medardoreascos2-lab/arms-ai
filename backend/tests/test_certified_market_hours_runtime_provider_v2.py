from datetime import date
from datetime import datetime
from datetime import time
from zoneinfo import ZoneInfo

import pytest

from backend.services.certified_market_calendar_v2 import (
    CertifiedCalendarSnapshotV2,
)
from backend.services.certified_market_hours_runtime_provider_v2 import (
    CertifiedMarketHoursRuntimeProviderV2,
)
from backend.services.market_hours_service_v2 import (
    MarketHoursServiceV2,
)
from backend.services.special_hours_snapshot_v2 import (
    CertifiedSpecialHoursSnapshotV2,
    CertifiedSpecialHoursWindowV2,
)


CHICAGO = ZoneInfo("America/Chicago")


def test_provider_builds_single_market_hours_service():
    provider = (
        CertifiedMarketHoursRuntimeProviderV2()
    )

    first = provider.get_market_hours_service()
    second = provider.get_market_hours_service()

    assert isinstance(
        first,
        MarketHoursServiceV2,
    )
    assert first is second


def test_provider_without_calendar_is_fail_closed():
    provider = (
        CertifiedMarketHoursRuntimeProviderV2()
    )

    service = provider.get_market_hours_service()

    timestamp = datetime(
        2026,
        8,
        18,
        10,
        0,
        tzinfo=CHICAGO,
    )

    assert (
        service.is_market_open(
            symbol="NQ",
            timestamp=timestamp,
        )
        is False
    )


def test_provider_uses_certified_open_calendar():
    snapshot = CertifiedCalendarSnapshotV2(
        covered_dates=frozenset(
            {
                date(2026, 8, 18),
            }
        ),
        closed_dates=frozenset(),
    )

    provider = (
        CertifiedMarketHoursRuntimeProviderV2(
            calendar_snapshot=snapshot,
        )
    )

    timestamp = datetime(
        2026,
        8,
        18,
        10,
        0,
        tzinfo=CHICAGO,
    )

    assert (
        provider
        .get_market_hours_service()
        .is_market_open(
            symbol="NQ",
            timestamp=timestamp,
        )
        is True
    )


def test_provider_uses_certified_closed_calendar():
    snapshot = CertifiedCalendarSnapshotV2(
        covered_dates=frozenset(
            {
                date(2026, 8, 18),
            }
        ),
        closed_dates=frozenset(
            {
                date(2026, 8, 18),
            }
        ),
    )

    provider = (
        CertifiedMarketHoursRuntimeProviderV2(
            calendar_snapshot=snapshot,
        )
    )

    timestamp = datetime(
        2026,
        8,
        18,
        10,
        0,
        tzinfo=CHICAGO,
    )

    assert (
        provider
        .get_market_hours_service()
        .is_market_open(
            symbol="NQ",
            timestamp=timestamp,
        )
        is False
    )


def test_provider_applies_certified_special_hours():
    calendar_snapshot = (
        CertifiedCalendarSnapshotV2(
            covered_dates=frozenset(
                {
                    date(2026, 8, 18),
                }
            ),
            closed_dates=frozenset(),
        )
    )

    special_snapshot = (
        CertifiedSpecialHoursSnapshotV2(
            windows=(
                CertifiedSpecialHoursWindowV2(
                    local_date=date(
                        2026,
                        8,
                        18,
                    ),
                    open_time=time(8, 30),
                    close_time=time(12, 0),
                ),
            )
        )
    )

    provider = (
        CertifiedMarketHoursRuntimeProviderV2(
            calendar_snapshot=(
                calendar_snapshot
            ),
            special_hours_snapshot=(
                special_snapshot
            ),
        )
    )

    service = provider.get_market_hours_service()

    inside = datetime(
        2026,
        8,
        18,
        10,
        0,
        tzinfo=CHICAGO,
    )

    outside = datetime(
        2026,
        8,
        18,
        13,
        0,
        tzinfo=CHICAGO,
    )

    assert (
        service.is_market_open(
            symbol="NQ",
            timestamp=inside,
        )
        is True
    )

    assert (
        service.is_market_open(
            symbol="NQ",
            timestamp=outside,
        )
        is False
    )


@pytest.mark.parametrize(
    (
        "keyword",
        "value",
    ),
    (
        (
            "calendar_snapshot",
            object(),
        ),
        (
            "special_hours_snapshot",
            object(),
        ),
    ),
)
def test_provider_rejects_invalid_snapshots(
    keyword,
    value,
):
    with pytest.raises(TypeError):
        CertifiedMarketHoursRuntimeProviderV2(
            **{
                keyword: value,
            }
        )
