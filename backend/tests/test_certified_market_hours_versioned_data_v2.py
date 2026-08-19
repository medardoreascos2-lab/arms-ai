from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.services.certified_market_hours_runtime_provider_v2 import (
    CertifiedMarketHoursRuntimeProviderV2,
)
from backend.services.certified_market_hours_snapshot_loader_v2 import (
    CertifiedMarketHoursSnapshotLoaderV2,
)


CHICAGO = ZoneInfo("America/Chicago")

DATA_FILE = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "market_hours"
    / "certified_market_hours_fixture_v2.json"
)


def test_versioned_certified_market_hours_file_exists():
    assert DATA_FILE.is_file()


def test_versioned_certified_market_hours_file_loads():
    loader = CertifiedMarketHoursSnapshotLoaderV2()

    calendar, special_hours = loader.load_from_file(
        file_path=DATA_FILE,
    )

    assert len(calendar.covered_dates) == 3
    assert len(calendar.closed_dates) == 0
    assert len(special_hours.windows) == 0


def test_versioned_data_can_build_runtime_provider():
    loader = CertifiedMarketHoursSnapshotLoaderV2()

    calendar, special_hours = loader.load_from_file(
        file_path=DATA_FILE,
    )

    provider = CertifiedMarketHoursRuntimeProviderV2(
        calendar_snapshot=calendar,
        special_hours_snapshot=special_hours,
    )

    service = provider.get_market_hours_service()

    assert service is provider.market_hours_service


def test_versioned_data_certifies_known_date():
    loader = CertifiedMarketHoursSnapshotLoaderV2()

    calendar, special_hours = loader.load_from_file(
        file_path=DATA_FILE,
    )

    provider = CertifiedMarketHoursRuntimeProviderV2(
        calendar_snapshot=calendar,
        special_hours_snapshot=special_hours,
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

    assert service.is_market_open(
        symbol="NQ",
        timestamp=timestamp,
    ) is True


def test_versioned_data_remains_fail_closed_outside_coverage():
    loader = CertifiedMarketHoursSnapshotLoaderV2()

    calendar, special_hours = loader.load_from_file(
        file_path=DATA_FILE,
    )

    provider = CertifiedMarketHoursRuntimeProviderV2(
        calendar_snapshot=calendar,
        special_hours_snapshot=special_hours,
    )

    service = provider.get_market_hours_service()

    timestamp = datetime(
        2026,
        8,
        20,
        10,
        0,
        tzinfo=CHICAGO,
    )

    assert service.is_market_open(
        symbol="NQ",
        timestamp=timestamp,
    ) is False
