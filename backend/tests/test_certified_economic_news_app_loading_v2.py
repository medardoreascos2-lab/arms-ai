from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from backend.api.app import create_app
from backend.config.api_settings import APISettings
from backend.services.certified_economic_news_data_lifecycle_v2 import (
    CertifiedEconomicNewsDataLifecycleV2,
)
from backend.services.economic_news_runtime_provider_v2 import (
    EconomicNewsRuntimeProviderV2,
)


CHICAGO = ZoneInfo("America/Chicago")


def _write_snapshot(
    path: Path,
    *,
    snapshot_version: str = "economic-news-app-v1",
) -> Path:
    payload = {
        "snapshot_version": snapshot_version,
        "generated_at": "2026-09-06T10:00:00-05:00",
        "coverage_start": "2026-09-06T08:00:00-05:00",
        "coverage_end": "2026-09-06T16:00:00-05:00",
        "high_impact_events": [
            "2026-09-06T09:30:00-05:00",
        ],
    }

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    return path


def _create_test_app(
    *,
    certified_economic_news_path: str | None,
):
    return create_app(
        settings=APISettings(
            certified_market_hours_path=None,
            certified_economic_news_path=(
                certified_economic_news_path
            ),
        )
    )


def test_app_publishes_economic_news_lifecycle_without_configured_path():
    app = _create_test_app(
        certified_economic_news_path=None,
    )

    lifecycle = (
        app.state.economic_news_data_lifecycle_v2
    )

    assert isinstance(
        lifecycle,
        CertifiedEconomicNewsDataLifecycleV2,
    )
    assert (
        lifecycle.get_status()
        == lifecycle.STATUS_EMPTY
    )
    assert lifecycle.get_active_snapshot() is None
    assert lifecycle.get_active_path() is None


def test_app_publishes_runtime_provider_without_configured_path():
    app = _create_test_app(
        certified_economic_news_path=None,
    )

    provider = (
        app.state.economic_news_runtime_provider_v2
    )

    assert isinstance(
        provider,
        EconomicNewsRuntimeProviderV2,
    )

    assert provider is (
        app.state.economic_news_data_lifecycle_v2
        .get_active_provider()
    )


def test_app_publishes_authority_without_configured_path():
    app = _create_test_app(
        certified_economic_news_path=None,
    )

    provider = (
        app.state.economic_news_runtime_provider_v2
    )
    authority = (
        app.state.economic_news_authority_v2
    )

    assert authority is (
        provider.get_economic_news_authority()
    )


def test_app_without_configured_snapshot_is_fail_closed():
    app = _create_test_app(
        certified_economic_news_path=None,
    )

    authority = (
        app.state.economic_news_authority_v2
    )

    timestamp = datetime(
        2026,
        9,
        6,
        12,
        0,
        tzinfo=CHICAGO,
    )

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=timestamp,
        )
        is True
    )


def test_app_loads_configured_certified_snapshot(
    tmp_path: Path,
):
    path = _write_snapshot(
        tmp_path / "economic-news.json"
    )

    app = _create_test_app(
        certified_economic_news_path=str(path),
    )

    lifecycle = (
        app.state.economic_news_data_lifecycle_v2
    )

    assert (
        lifecycle.get_status()
        == lifecycle.STATUS_READY
    )

    snapshot = lifecycle.get_active_snapshot()

    assert snapshot is not None
    assert (
        snapshot.snapshot_version
        == "economic-news-app-v1"
    )
    assert lifecycle.get_active_path() == path


def test_app_configured_provider_is_lifecycle_active_provider(
    tmp_path: Path,
):
    path = _write_snapshot(
        tmp_path / "economic-news.json"
    )

    app = _create_test_app(
        certified_economic_news_path=str(path),
    )

    lifecycle = (
        app.state.economic_news_data_lifecycle_v2
    )
    provider = (
        app.state.economic_news_runtime_provider_v2
    )

    assert provider is lifecycle.get_active_provider()
    assert provider.snapshot is (
        lifecycle.get_active_snapshot()
    )


def test_app_configured_authority_is_provider_authority(
    tmp_path: Path,
):
    path = _write_snapshot(
        tmp_path / "economic-news.json"
    )

    app = _create_test_app(
        certified_economic_news_path=str(path),
    )

    provider = (
        app.state.economic_news_runtime_provider_v2
    )
    authority = (
        app.state.economic_news_authority_v2
    )

    assert authority is (
        provider.get_economic_news_authority()
    )


def test_app_configured_authority_blocks_exact_high_impact_event(
    tmp_path: Path,
):
    path = _write_snapshot(
        tmp_path / "economic-news.json"
    )

    app = _create_test_app(
        certified_economic_news_path=str(path),
    )

    authority = (
        app.state.economic_news_authority_v2
    )

    event = datetime(
        2026,
        9,
        6,
        9,
        30,
        tzinfo=CHICAGO,
    )

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=event,
        )
        is True
    )


def test_app_configured_authority_allows_clear_timestamp_inside_coverage(
    tmp_path: Path,
):
    path = _write_snapshot(
        tmp_path / "economic-news.json"
    )

    app = _create_test_app(
        certified_economic_news_path=str(path),
    )

    authority = (
        app.state.economic_news_authority_v2
    )

    clear_timestamp = datetime(
        2026,
        9,
        6,
        12,
        0,
        tzinfo=CHICAGO,
    )

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=clear_timestamp,
        )
        is False
    )


def test_app_configured_authority_blocks_outside_snapshot_coverage(
    tmp_path: Path,
):
    path = _write_snapshot(
        tmp_path / "economic-news.json"
    )

    app = _create_test_app(
        certified_economic_news_path=str(path),
    )

    authority = (
        app.state.economic_news_authority_v2
    )

    outside = datetime(
        2026,
        9,
        6,
        17,
        0,
        tzinfo=CHICAGO,
    )

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=outside,
        )
        is True
    )


def test_app_invalid_configured_snapshot_fails_startup(
    tmp_path: Path,
):
    path = tmp_path / "invalid-economic-news.json"

    path.write_text(
        json.dumps(
            {
                "snapshot_version": "broken",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        _create_test_app(
            certified_economic_news_path=str(path),
        )


def test_app_missing_configured_snapshot_fails_startup(
    tmp_path: Path,
):
    missing_path = (
        tmp_path / "missing-economic-news.json"
    )

    with pytest.raises(FileNotFoundError):
        _create_test_app(
            certified_economic_news_path=(
                str(missing_path)
            ),
        )
