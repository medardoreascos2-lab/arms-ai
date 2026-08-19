import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from backend.api.app import create_app
from backend.config.api_settings import APISettings


def _write_snapshot(
    tmp_path,
    *,
    covered_dates,
    closed_dates=None,
    special_hours=None,
):
    path = tmp_path / "certified-market-hours.json"

    path.write_text(
        json.dumps(
            {
                "covered_dates": covered_dates,
                "closed_dates": closed_dates or [],
                "special_hours": special_hours or [],
            }
        ),
        encoding="utf-8",
    )

    return path


def test_create_app_without_certified_path_remains_fail_closed():
    app = create_app(
        settings=APISettings(
            certified_market_hours_path=None,
        )
    )

    provider = (
        app.state.market_hours_runtime_provider_v2
    )

    service = app.state.market_hours_service_v2

    assert provider.calendar_snapshot is None

    assert (
        service.is_market_open(
            symbol="NQ",
            timestamp=datetime(
                2026,
                8,
                18,
                10,
                0,
                tzinfo=ZoneInfo("America/Chicago"),
            ),
        )
        is False
    )


def test_create_app_loads_configured_certified_snapshot(
    tmp_path,
):
    path = _write_snapshot(
        tmp_path,
        covered_dates=["2026-08-18"],
    )

    app = create_app(
        settings=APISettings(
            certified_market_hours_path=str(path),
        )
    )

    provider = (
        app.state.market_hours_runtime_provider_v2
    )

    service = app.state.market_hours_service_v2

    assert provider.calendar_snapshot is not None

    assert (
        service.is_market_open(
            symbol="NQ",
            timestamp=datetime(
                2026,
                8,
                18,
                10,
                0,
                tzinfo=ZoneInfo("America/Chicago"),
            ),
        )
        is True
    )


def test_create_app_configured_snapshot_stays_fail_closed_outside_coverage(
    tmp_path,
):
    path = _write_snapshot(
        tmp_path,
        covered_dates=["2026-08-18"],
    )

    app = create_app(
        settings=APISettings(
            certified_market_hours_path=str(path),
        )
    )

    service = app.state.market_hours_service_v2

    assert (
        service.is_market_open(
            symbol="NQ",
            timestamp=datetime(
                2026,
                8,
                19,
                10,
                0,
                tzinfo=ZoneInfo("America/Chicago"),
            ),
        )
        is False
    )


def test_create_app_configured_missing_snapshot_fails_startup(
    tmp_path,
):
    missing = (
        tmp_path / "missing-certified-hours.json"
    )

    with pytest.raises(FileNotFoundError):
        create_app(
            settings=APISettings(
                certified_market_hours_path=(
                    str(missing)
                ),
            )
        )


def test_create_app_configured_invalid_snapshot_fails_startup(
    tmp_path,
):
    path = (
        tmp_path / "invalid-certified-hours.json"
    )

    path.write_text(
        "{not-json",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        create_app(
            settings=APISettings(
                certified_market_hours_path=(
                    str(path)
                ),
            )
        )


def test_create_app_exposes_market_hours_data_lifecycle_v2(
    tmp_path,
):
    path = _write_snapshot(
        tmp_path,
        covered_dates=["2026-08-18"],
    )

    app = create_app(
        settings=APISettings(
            certified_market_hours_path=str(path),
        )
    )

    lifecycle = (
        app.state.market_hours_data_lifecycle_v2
    )

    provider = (
        app.state.market_hours_runtime_provider_v2
    )

    assert lifecycle.get_status() == "READY"
    assert lifecycle.get_active_provider() is provider
    assert lifecycle.get_active_path() == path



def test_create_app_exposes_runtime_refresh_service_v2(
    tmp_path,
):
    path = _write_snapshot(
        tmp_path,
        covered_dates=["2026-08-18"],
    )

    app = create_app(
        settings=APISettings(
            certified_market_hours_path=str(path),
        )
    )

    refresh_service = (
        app.state
        .market_hours_runtime_refresh_service_v2
    )

    assert (
        refresh_service.app_state
        is app.state
    )
    assert (
        refresh_service.lifecycle
        is app.state.market_hours_data_lifecycle_v2
    )


def test_create_app_refresh_service_uses_same_runtime_state(
    tmp_path,
):
    path = _write_snapshot(
        tmp_path,
        covered_dates=["2026-08-18"],
    )

    app = create_app(
        settings=APISettings(
            certified_market_hours_path=str(path),
        )
    )

    refresh_service = (
        app.state
        .market_hours_runtime_refresh_service_v2
    )

    assert (
        refresh_service.lifecycle.get_active_provider()
        is app.state.market_hours_runtime_provider_v2
    )


def test_create_app_without_certified_path_exposes_empty_lifecycle():
    app = create_app(
        settings=APISettings(
            certified_market_hours_path=None,
        )
    )

    lifecycle = (
        app.state.market_hours_data_lifecycle_v2
    )

    assert lifecycle.get_status() == "EMPTY"
    assert lifecycle.get_active_provider() is None
    assert lifecycle.get_active_path() is None
