from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.certified_economic_news_data_lifecycle_v2 import (
    CertifiedEconomicNewsDataLifecycleV2,
)
from backend.services.certified_economic_news_snapshot_loader_v2 import (
    CertifiedEconomicNewsSnapshotLoaderV2,
)
from backend.services.certified_economic_news_snapshot_v2 import (
    CertifiedEconomicNewsSnapshotV2,
)
from backend.services.economic_news_runtime_provider_v2 import (
    EconomicNewsRuntimeProviderV2,
)


def _mapping(
    *,
    version: str = "v1",
    coverage_start: str = "2026-09-06T00:00:00+00:00",
    coverage_end: str = "2026-09-06T23:59:00+00:00",
    events: list[str] | None = None,
) -> dict[str, object]:
    return {
        "snapshot_version": version,
        "generated_at": "2026-09-06T00:00:00+00:00",
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
        "high_impact_events": (
            []
            if events is None
            else events
        ),
    }


def _write_snapshot(
    tmp_path: Path,
    *,
    name: str = "economic_news.json",
    mapping: dict[str, object] | None = None,
) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            _mapping()
            if mapping is None
            else mapping
        ),
        encoding="utf-8",
    )
    return path


def test_initial_status_is_empty():
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    assert lifecycle.get_status() == lifecycle.STATUS_EMPTY


def test_initial_active_path_is_none():
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    assert lifecycle.get_active_path() is None


def test_initial_active_snapshot_is_none():
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    assert lifecycle.get_active_snapshot() is None


def test_initial_provider_exists_fail_closed():
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    provider = lifecycle.get_active_provider()

    assert isinstance(
        provider,
        EconomicNewsRuntimeProviderV2,
    )

    assert (
        provider.is_timestamp_covered(
            timestamp=__import__(
                "datetime"
            ).datetime.fromisoformat(
                "2026-09-06T12:00:00+00:00"
            ),
        )
        is False
    )

    authority = (
        provider.get_economic_news_authority()
    )

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=__import__(
                "datetime"
            ).datetime.fromisoformat(
                "2026-09-06T12:00:00+00:00"
            ),
        )
        is True
    )


def test_initial_activation_report_is_none():
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    assert lifecycle.get_last_activation_report() is None


def test_accepts_explicit_loader():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    lifecycle = CertifiedEconomicNewsDataLifecycleV2(
        loader=loader,
    )

    assert lifecycle.loader is loader


def test_rejects_invalid_loader_type():
    with pytest.raises(TypeError):
        CertifiedEconomicNewsDataLifecycleV2(
            loader=object(),
        )


def test_activate_from_file_sets_ready_state(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()
    path = _write_snapshot(tmp_path)

    report = lifecycle.activate_from_file(
        file_path=path,
    )

    assert lifecycle.get_status() == lifecycle.STATUS_READY
    assert report["success"] is True
    assert report["status"] == lifecycle.STATUS_READY


def test_activate_from_file_sets_active_path(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()
    path = _write_snapshot(tmp_path)

    lifecycle.activate_from_file(
        file_path=path,
    )

    assert lifecycle.get_active_path() == path


def test_activate_from_file_sets_active_snapshot(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()
    path = _write_snapshot(
        tmp_path,
        mapping=_mapping(
            version="certified-v9",
        ),
    )

    lifecycle.activate_from_file(
        file_path=path,
    )

    snapshot = lifecycle.get_active_snapshot()

    assert isinstance(
        snapshot,
        CertifiedEconomicNewsSnapshotV2,
    )
    assert (
        snapshot.snapshot_version
        == "certified-v9"
    )


def test_activate_from_file_sets_active_provider(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()
    path = _write_snapshot(tmp_path)

    initial_provider = lifecycle.get_active_provider()

    lifecycle.activate_from_file(
        file_path=path,
    )

    provider = lifecycle.get_active_provider()

    assert isinstance(
        provider,
        EconomicNewsRuntimeProviderV2,
    )
    assert provider is not initial_provider


def test_active_provider_uses_active_snapshot(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    event = "2026-09-06T14:30:00+00:00"

    path = _write_snapshot(
        tmp_path,
        mapping=_mapping(
            events=[event],
        ),
    )

    lifecycle.activate_from_file(
        file_path=path,
    )

    provider = lifecycle.get_active_provider()

    assert (
        provider.snapshot
        is lifecycle.get_active_snapshot()
    )

    authority = (
        provider.get_economic_news_authority()
    )

    timestamp = __import__(
        "datetime"
    ).datetime.fromisoformat(event)

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=timestamp,
        )
        is True
    )


def test_activation_report_contains_explicit_coverage(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    path = _write_snapshot(
        tmp_path,
        mapping=_mapping(
            coverage_start=(
                "2026-09-06T08:00:00+00:00"
            ),
            coverage_end=(
                "2026-09-06T18:00:00+00:00"
            ),
        ),
    )

    report = lifecycle.activate_from_file(
        file_path=path,
    )

    assert report["coverage_start"] == (
        "2026-09-06T08:00:00+00:00"
    )
    assert report["coverage_end"] == (
        "2026-09-06T18:00:00+00:00"
    )


def test_activation_report_contains_snapshot_version(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    path = _write_snapshot(
        tmp_path,
        mapping=_mapping(
            version="v42",
        ),
    )

    report = lifecycle.activate_from_file(
        file_path=path,
    )

    assert report["snapshot_version"] == "v42"


def test_activation_report_contains_event_count(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    path = _write_snapshot(
        tmp_path,
        mapping=_mapping(
            events=[
                "2026-09-06T09:00:00+00:00",
                "2026-09-06T14:00:00+00:00",
            ],
        ),
    )

    report = lifecycle.activate_from_file(
        file_path=path,
    )

    assert report["high_impact_events"] == 2


def test_failed_activation_preserves_previous_provider(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    valid_path = _write_snapshot(
        tmp_path,
        name="valid.json",
    )

    lifecycle.activate_from_file(
        file_path=valid_path,
    )

    previous = lifecycle.get_active_provider()

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(
        "{broken",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        lifecycle.activate_from_file(
            file_path=invalid_path,
        )

    assert lifecycle.get_active_provider() is previous


def test_failed_activation_preserves_previous_snapshot(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    valid_path = _write_snapshot(
        tmp_path,
        name="valid.json",
        mapping=_mapping(
            version="good",
        ),
    )

    lifecycle.activate_from_file(
        file_path=valid_path,
    )

    previous = lifecycle.get_active_snapshot()

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(
        "{broken",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        lifecycle.activate_from_file(
            file_path=invalid_path,
        )

    assert lifecycle.get_active_snapshot() is previous


def test_failed_activation_preserves_previous_path(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    valid_path = _write_snapshot(
        tmp_path,
        name="valid.json",
    )

    lifecycle.activate_from_file(
        file_path=valid_path,
    )

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(
        "{broken",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        lifecycle.activate_from_file(
            file_path=invalid_path,
        )

    assert lifecycle.get_active_path() == valid_path


def test_failed_activation_preserves_previous_ready_status(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    valid_path = _write_snapshot(
        tmp_path,
        name="valid.json",
    )

    lifecycle.activate_from_file(
        file_path=valid_path,
    )

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(
        "{broken",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        lifecycle.activate_from_file(
            file_path=invalid_path,
        )

    assert lifecycle.get_status() == lifecycle.STATUS_READY


def test_failed_activation_updates_failure_report(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(
        "{broken",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        lifecycle.activate_from_file(
            file_path=invalid_path,
        )

    report = lifecycle.get_last_activation_report()

    assert report is not None
    assert report["success"] is False
    assert report["status"] == lifecycle.STATUS_FAILED
    assert report["source"] == str(invalid_path)

    error = report["error"]

    assert isinstance(error, dict)
    assert error["type"] == "ValueError"


def test_get_last_activation_report_returns_copy(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()
    path = _write_snapshot(tmp_path)

    lifecycle.activate_from_file(
        file_path=path,
    )

    first = lifecycle.get_last_activation_report()
    second = lifecycle.get_last_activation_report()

    assert first == second
    assert first is not second


def test_create_runtime_checkpoint_captures_identity(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()
    path = _write_snapshot(tmp_path)

    lifecycle.activate_from_file(
        file_path=path,
    )

    checkpoint = (
        lifecycle.create_runtime_checkpoint()
    )

    assert (
        checkpoint["active_provider"]
        is lifecycle.get_active_provider()
    )
    assert (
        checkpoint["active_snapshot"]
        is lifecycle.get_active_snapshot()
    )
    assert (
        checkpoint["active_path"]
        == lifecycle.get_active_path()
    )
    assert (
        checkpoint["status"]
        == lifecycle.get_status()
    )


def test_restore_runtime_checkpoint_restores_runtime_identity(tmp_path):
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    first_path = _write_snapshot(
        tmp_path,
        name="first.json",
        mapping=_mapping(
            version="first",
        ),
    )

    lifecycle.activate_from_file(
        file_path=first_path,
    )

    checkpoint = (
        lifecycle.create_runtime_checkpoint()
    )

    second_path = _write_snapshot(
        tmp_path,
        name="second.json",
        mapping=_mapping(
            version="second",
        ),
    )

    lifecycle.activate_from_file(
        file_path=second_path,
    )

    lifecycle.restore_runtime_checkpoint(
        checkpoint=checkpoint,
    )

    assert (
        lifecycle.get_active_provider()
        is checkpoint["active_provider"]
    )
    assert (
        lifecycle.get_active_snapshot()
        is checkpoint["active_snapshot"]
    )
    assert (
        lifecycle.get_active_path()
        == checkpoint["active_path"]
    )
    assert (
        lifecycle.get_status()
        == checkpoint["status"]
    )


def test_restore_runtime_checkpoint_rejects_non_dict():
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    with pytest.raises(TypeError):
        lifecycle.restore_runtime_checkpoint(
            checkpoint=object(),
        )


def test_restore_runtime_checkpoint_rejects_wrong_keys():
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    with pytest.raises(ValueError):
        lifecycle.restore_runtime_checkpoint(
            checkpoint={
                "status": lifecycle.STATUS_EMPTY,
            },
        )


def test_lifecycle_has_no_arbitrary_event_window_state():
    lifecycle = CertifiedEconomicNewsDataLifecycleV2()

    forbidden = {
        "window_minutes",
        "event_window",
        "pre_event_window",
        "post_event_window",
    }

    assert forbidden.isdisjoint(
        vars(lifecycle)
    )
