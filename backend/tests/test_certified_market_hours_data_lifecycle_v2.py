import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from backend.services.certified_market_hours_data_lifecycle_v2 import (
    CertifiedMarketHoursDataLifecycleV2,
)
from backend.services.certified_market_hours_runtime_provider_v2 import (
    CertifiedMarketHoursRuntimeProviderV2,
)


def write_snapshot(
    tmp_path,
    *,
    covered_dates=None,
    closed_dates=None,
    special_hours=None,
):
    path = tmp_path / "certified_market_hours.json"

    path.write_text(
        json.dumps(
            {
                "covered_dates": (
                    covered_dates
                    if covered_dates is not None
                    else ["2026-08-18"]
                ),
                "closed_dates": (
                    closed_dates
                    if closed_dates is not None
                    else []
                ),
                "special_hours": (
                    special_hours
                    if special_hours is not None
                    else []
                ),
            }
        ),
        encoding="utf-8",
    )

    return path


def test_lifecycle_starts_empty():
    lifecycle = CertifiedMarketHoursDataLifecycleV2()

    assert lifecycle.get_status() == "EMPTY"
    assert lifecycle.get_active_provider() is None
    assert lifecycle.get_active_path() is None
    assert lifecycle.get_last_activation_report() is None


def test_activate_valid_snapshot(tmp_path):
    path = write_snapshot(tmp_path)

    lifecycle = CertifiedMarketHoursDataLifecycleV2()

    report = lifecycle.activate_from_file(
        file_path=path,
    )

    assert report["success"] is True
    assert report["status"] == "READY"
    assert report["covered_dates"] == 1
    assert report["closed_dates"] == 0
    assert report["special_hours"] == 0

    provider = lifecycle.get_active_provider()

    assert isinstance(
        provider,
        CertifiedMarketHoursRuntimeProviderV2,
    )

    assert lifecycle.get_active_path() == path
    assert lifecycle.get_status() == "READY"

    assert (
        provider
        .get_market_hours_service()
        .is_market_open(
            symbol="NQ",
            timestamp=datetime(
                2026,
                8,
                18,
                10,
                0,
                tzinfo=ZoneInfo(
                    "America/Chicago"
                ),
            ),
        )
        is True
    )


def test_invalid_snapshot_does_not_activate(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text(
        "{not-json",
        encoding="utf-8",
    )

    lifecycle = CertifiedMarketHoursDataLifecycleV2()

    with pytest.raises(ValueError):
        lifecycle.activate_from_file(
            file_path=path,
        )

    assert lifecycle.get_status() == "EMPTY"
    assert lifecycle.get_active_provider() is None
    assert lifecycle.get_active_path() is None

    report = lifecycle.get_last_activation_report()

    assert report is not None
    assert report["success"] is False
    assert report["status"] == "FAILED"
    assert report["error"]["type"] == "ValueError"


def test_failed_replacement_preserves_active_provider(
    tmp_path,
):
    valid_path = write_snapshot(tmp_path)

    lifecycle = CertifiedMarketHoursDataLifecycleV2()

    lifecycle.activate_from_file(
        file_path=valid_path,
    )

    original_provider = (
        lifecycle.get_active_provider()
    )
    original_path = lifecycle.get_active_path()

    invalid_path = tmp_path / "broken.json"
    invalid_path.write_text(
        "{}",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        lifecycle.activate_from_file(
            file_path=invalid_path,
        )

    assert lifecycle.get_status() == "READY"
    assert (
        lifecycle.get_active_provider()
        is original_provider
    )
    assert lifecycle.get_active_path() == original_path

    report = lifecycle.get_last_activation_report()

    assert report is not None
    assert report["success"] is False
    assert report["status"] == "FAILED"


def test_missing_file_preserves_empty_state(tmp_path):
    lifecycle = CertifiedMarketHoursDataLifecycleV2()

    path = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError):
        lifecycle.activate_from_file(
            file_path=path,
        )

    assert lifecycle.get_status() == "EMPTY"
    assert lifecycle.get_active_provider() is None


def test_outside_coverage_remains_fail_closed(
    tmp_path,
):
    path = write_snapshot(tmp_path)

    lifecycle = CertifiedMarketHoursDataLifecycleV2()

    lifecycle.activate_from_file(
        file_path=path,
    )

    provider = lifecycle.get_active_provider()

    assert provider is not None

    assert (
        provider
        .get_market_hours_service()
        .is_market_open(
            symbol="NQ",
            timestamp=datetime(
                2026,
                8,
                19,
                10,
                0,
                tzinfo=ZoneInfo(
                    "America/Chicago"
                ),
            ),
        )
        is False
    )


def test_rejects_invalid_loader():
    with pytest.raises(
        TypeError,
        match="loader",
    ):
        CertifiedMarketHoursDataLifecycleV2(
            loader=object(),
        )


def test_runtime_checkpoint_restores_active_state(
    tmp_path,
):
    path = write_snapshot(tmp_path)

    lifecycle = CertifiedMarketHoursDataLifecycleV2()

    lifecycle.activate_from_file(
        file_path=path,
    )

    original_provider = lifecycle.get_active_provider()
    original_path = lifecycle.get_active_path()
    original_status = lifecycle.get_status()
    original_report = lifecycle.get_last_activation_report()

    checkpoint = lifecycle.create_runtime_checkpoint()

    second_dir = tmp_path / "second"
    second_dir.mkdir()

    second_path = write_snapshot(
        second_dir,
    )

    lifecycle.activate_from_file(
        file_path=second_path,
    )

    assert (
        lifecycle.get_active_provider()
        is not original_provider
    )

    lifecycle.restore_runtime_checkpoint(
        checkpoint=checkpoint,
    )

    assert (
        lifecycle.get_active_provider()
        is original_provider
    )
    assert lifecycle.get_active_path() == original_path
    assert lifecycle.get_status() == original_status
    assert (
        lifecycle.get_last_activation_report()
        == original_report
    )


def test_activation_report_exposes_coverage_range(
    tmp_path,
):
    lifecycle = CertifiedMarketHoursDataLifecycleV2()

    path = write_snapshot(
        tmp_path,
        covered_dates=[
            "2026-08-20",
            "2026-08-18",
            "2026-08-19",
        ],
    )

    report = lifecycle.activate_from_file(
        file_path=path,
    )

    assert report["coverage_start"] == "2026-08-18"
    assert report["coverage_end"] == "2026-08-20"
    assert report["covered_dates"] == 3


def test_activation_report_empty_coverage_has_no_range(
    tmp_path,
):
    lifecycle = CertifiedMarketHoursDataLifecycleV2()

    path = write_snapshot(
        tmp_path,
        covered_dates=[],
    )

    report = lifecycle.activate_from_file(
        file_path=path,
    )

    assert report["success"] is True
    assert report["coverage_start"] is None
    assert report["coverage_end"] is None
    assert report["covered_dates"] == 0
