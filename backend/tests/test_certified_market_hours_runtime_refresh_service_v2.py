import json
from types import SimpleNamespace

import pytest

from backend.services.certified_market_hours_data_lifecycle_v2 import (
    CertifiedMarketHoursDataLifecycleV2,
)
from backend.services.certified_market_hours_runtime_provider_v2 import (
    CertifiedMarketHoursRuntimeProviderV2,
)
from backend.services.certified_market_hours_runtime_refresh_service_v2 import (
    CertifiedMarketHoursRuntimeRefreshServiceV2,
)


def _write_snapshot(
    tmp_path,
    *,
    filename="market-hours.json",
):
    path = tmp_path / filename

    payload = {
        "covered_dates": [
            "2026-08-18",
        ],
        "closed_dates": [],
        "special_hours": [],
    }

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    return path


def test_refresh_publishes_new_runtime_state(
    tmp_path,
):
    lifecycle = (
        CertifiedMarketHoursDataLifecycleV2()
    )

    old_provider = (
        CertifiedMarketHoursRuntimeProviderV2()
    )

    old_service = (
        old_provider.get_market_hours_service()
    )

    app_state = SimpleNamespace(
        market_hours_runtime_provider_v2=(
            old_provider
        ),
        market_hours_service_v2=old_service,
    )

    refresh_service = (
        CertifiedMarketHoursRuntimeRefreshServiceV2(
            app_state=app_state,
            lifecycle=lifecycle,
        )
    )

    path = _write_snapshot(tmp_path)

    report = refresh_service.refresh_from_file(
        file_path=path,
    )

    new_provider = (
        app_state.market_hours_runtime_provider_v2
    )
    new_service = (
        app_state.market_hours_service_v2
    )

    assert report["success"] is True
    assert report["runtime_published"] is True

    assert new_provider is (
        lifecycle.get_active_provider()
    )
    assert new_provider is not old_provider
    assert new_service is (
        new_provider.get_market_hours_service()
    )
    assert new_service is not old_service


def test_failed_refresh_preserves_runtime_state(
    tmp_path,
):
    lifecycle = (
        CertifiedMarketHoursDataLifecycleV2()
    )

    valid_path = _write_snapshot(
        tmp_path,
        filename="valid.json",
    )

    lifecycle.activate_from_file(
        file_path=valid_path,
    )

    old_provider = (
        lifecycle.get_active_provider()
    )

    assert old_provider is not None

    old_service = (
        old_provider.get_market_hours_service()
    )

    app_state = SimpleNamespace(
        market_hours_runtime_provider_v2=(
            old_provider
        ),
        market_hours_service_v2=old_service,
    )

    refresh_service = (
        CertifiedMarketHoursRuntimeRefreshServiceV2(
            app_state=app_state,
            lifecycle=lifecycle,
        )
    )

    missing_path = (
        tmp_path / "missing.json"
    )

    with pytest.raises(
        FileNotFoundError
    ):
        refresh_service.refresh_from_file(
            file_path=missing_path,
        )

    assert (
        app_state.market_hours_runtime_provider_v2
        is old_provider
    )
    assert (
        app_state.market_hours_service_v2
        is old_service
    )

    assert (
        lifecycle.get_active_provider()
        is old_provider
    )


def test_refresh_rejects_missing_app_state():
    lifecycle = (
        CertifiedMarketHoursDataLifecycleV2()
    )

    with pytest.raises(
        ValueError,
        match="app_state",
    ):
        CertifiedMarketHoursRuntimeRefreshServiceV2(
            app_state=None,
            lifecycle=lifecycle,
        )


def test_refresh_rejects_invalid_lifecycle():
    with pytest.raises(
        TypeError,
        match="lifecycle",
    ):
        CertifiedMarketHoursRuntimeRefreshServiceV2(
            app_state=SimpleNamespace(),
            lifecycle=object(),
        )


def test_post_activation_failure_restores_lifecycle_and_app_state(
    tmp_path,
    monkeypatch,
):
    lifecycle = CertifiedMarketHoursDataLifecycleV2()

    original_path = _write_snapshot(
        tmp_path,
        filename="original.json",
    )

    lifecycle.activate_from_file(
        file_path=original_path,
    )

    old_provider = lifecycle.get_active_provider()
    old_lifecycle_path = lifecycle.get_active_path()
    old_lifecycle_status = lifecycle.get_status()
    old_report = lifecycle.get_last_activation_report()

    assert old_provider is not None

    old_service = old_provider.get_market_hours_service()

    app_state = SimpleNamespace(
        market_hours_runtime_provider_v2=old_provider,
        market_hours_service_v2=old_service,
    )

    refresh_service = (
        CertifiedMarketHoursRuntimeRefreshServiceV2(
            app_state=app_state,
            lifecycle=lifecycle,
        )
    )

    replacement_path = _write_snapshot(
        tmp_path,
        filename="replacement.json",
    )

    def fail_after_activation():
        raise RuntimeError(
            "synthetic post-activation failure"
        )

    monkeypatch.setattr(
        lifecycle,
        "get_active_provider",
        fail_after_activation,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic post-activation failure",
    ):
        refresh_service.refresh_from_file(
            file_path=replacement_path,
        )

    assert (
        app_state.market_hours_runtime_provider_v2
        is old_provider
    )
    assert (
        app_state.market_hours_service_v2
        is old_service
    )

    assert lifecycle._active_provider is old_provider
    assert lifecycle.get_active_path() == old_lifecycle_path
    assert lifecycle.get_status() == old_lifecycle_status
    assert (
        lifecycle.get_last_activation_report()
        == old_report
    )
