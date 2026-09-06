from __future__ import annotations

import json
from datetime import datetime
from datetime import timezone

import pytest

from backend.services.certified_economic_news_snapshot_loader_v2 import (
    CertifiedEconomicNewsSnapshotLoaderV2,
)
from backend.services.certified_economic_news_snapshot_v2 import (
    CertifiedEconomicNewsSnapshotV2,
)


def valid_mapping() -> dict[str, object]:
    return {
        "snapshot_version": "v2",
        "generated_at": "2026-09-06T12:00:00+00:00",
        "coverage_start": "2026-09-06T07:00:00-05:00",
        "coverage_end": "2026-09-06T16:00:00-05:00",
        "high_impact_events": [
            "2026-09-06T09:30:00-05:00",
            "2026-09-06T14:00:00-05:00",
        ],
    }


def test_load_from_mapping_returns_certified_snapshot():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    snapshot = loader.load_from_mapping(
        raw=valid_mapping(),
    )

    assert isinstance(
        snapshot,
        CertifiedEconomicNewsSnapshotV2,
    )


def test_loader_preserves_snapshot_version():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    snapshot = loader.load_from_mapping(
        raw=valid_mapping(),
    )

    assert snapshot.snapshot_version == "v2"


def test_loader_parses_generated_at_as_aware_datetime():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    snapshot = loader.load_from_mapping(
        raw=valid_mapping(),
    )

    assert isinstance(snapshot.generated_at, datetime)
    assert snapshot.generated_at.tzinfo is not None


def test_loader_parses_coverage_boundaries_as_aware_datetimes():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    snapshot = loader.load_from_mapping(
        raw=valid_mapping(),
    )

    assert snapshot.coverage_start.tzinfo is not None
    assert snapshot.coverage_end.tzinfo is not None


def test_loader_parses_high_impact_events_as_frozenset():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    snapshot = loader.load_from_mapping(
        raw=valid_mapping(),
    )

    assert isinstance(
        snapshot.high_impact_events,
        frozenset,
    )
    assert len(snapshot.high_impact_events) == 2

    assert all(
        event.tzinfo is not None
        for event in snapshot.high_impact_events
    )


def test_loader_accepts_explicit_empty_event_set():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    raw = valid_mapping()
    raw["high_impact_events"] = []

    snapshot = loader.load_from_mapping(raw=raw)

    assert snapshot.high_impact_events == frozenset()


def test_loader_rejects_non_mapping_document():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    with pytest.raises(TypeError):
        loader.load_from_mapping(raw=[])


@pytest.mark.parametrize(
    "field",
    [
        "snapshot_version",
        "generated_at",
        "coverage_start",
        "coverage_end",
        "high_impact_events",
    ],
)
def test_loader_rejects_missing_required_field(field):
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    raw = valid_mapping()
    del raw[field]

    with pytest.raises(ValueError, match="obligatorio"):
        loader.load_from_mapping(raw=raw)


def test_loader_rejects_unknown_top_level_field():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    raw = valid_mapping()
    raw["unexpected"] = True

    with pytest.raises(ValueError, match="desconocido"):
        loader.load_from_mapping(raw=raw)


@pytest.mark.parametrize(
    "field",
    [
        "generated_at",
        "coverage_start",
        "coverage_end",
    ],
)
def test_loader_rejects_non_string_timestamp(field):
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    raw = valid_mapping()
    raw[field] = object()

    with pytest.raises(TypeError, match=field):
        loader.load_from_mapping(raw=raw)


@pytest.mark.parametrize(
    "field",
    [
        "generated_at",
        "coverage_start",
        "coverage_end",
    ],
)
def test_loader_rejects_invalid_iso_timestamp(field):
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    raw = valid_mapping()
    raw[field] = "not-a-timestamp"

    with pytest.raises(ValueError, match=field):
        loader.load_from_mapping(raw=raw)


@pytest.mark.parametrize(
    "field",
    [
        "generated_at",
        "coverage_start",
        "coverage_end",
    ],
)
def test_loader_rejects_naive_timestamp(field):
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    raw = valid_mapping()
    raw[field] = "2026-09-06T12:00:00"

    with pytest.raises(ValueError, match="timezone"):
        loader.load_from_mapping(raw=raw)


def test_loader_rejects_non_list_high_impact_events():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    raw = valid_mapping()
    raw["high_impact_events"] = (
        "2026-09-06T09:30:00-05:00",
    )

    with pytest.raises(
        TypeError,
        match="high_impact_events",
    ):
        loader.load_from_mapping(raw=raw)


def test_loader_rejects_non_string_event_timestamp():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    raw = valid_mapping()
    raw["high_impact_events"] = [object()]

    with pytest.raises(
        TypeError,
        match="high_impact_events",
    ):
        loader.load_from_mapping(raw=raw)


def test_loader_rejects_invalid_event_timestamp():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    raw = valid_mapping()
    raw["high_impact_events"] = ["not-a-timestamp"]

    with pytest.raises(
        ValueError,
        match="high_impact_events",
    ):
        loader.load_from_mapping(raw=raw)


def test_loader_rejects_naive_event_timestamp():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    raw = valid_mapping()
    raw["high_impact_events"] = [
        "2026-09-06T09:30:00"
    ]

    with pytest.raises(ValueError, match="timezone"):
        loader.load_from_mapping(raw=raw)


def test_loader_rejects_duplicate_event_timestamps():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    raw = valid_mapping()
    raw["high_impact_events"] = [
        "2026-09-06T09:30:00-05:00",
        "2026-09-06T09:30:00-05:00",
    ]

    with pytest.raises(ValueError, match="duplic"):
        loader.load_from_mapping(raw=raw)


def test_loader_delegates_event_outside_coverage_rejection():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    raw = valid_mapping()
    raw["high_impact_events"] = [
        "2026-09-06T18:00:00-05:00"
    ]

    with pytest.raises(ValueError):
        loader.load_from_mapping(raw=raw)


def test_load_from_file_reads_explicit_json(tmp_path):
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    path = tmp_path / "economic_news.json"

    path.write_text(
        json.dumps(valid_mapping()),
        encoding="utf-8",
    )

    snapshot = loader.load_from_file(
        file_path=path,
    )

    assert isinstance(
        snapshot,
        CertifiedEconomicNewsSnapshotV2,
    )


def test_load_from_file_rejects_missing_file(tmp_path):
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    path = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError):
        loader.load_from_file(
            file_path=path,
        )


def test_load_from_file_rejects_invalid_json(tmp_path):
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    path = tmp_path / "invalid.json"
    path.write_text(
        "{invalid",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="JSON"):
        loader.load_from_file(
            file_path=path,
        )


def test_load_from_file_rejects_directory(tmp_path):
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    with pytest.raises(IsADirectoryError):
        loader.load_from_file(
            file_path=tmp_path,
        )


def test_load_from_file_rejects_blank_string_path():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    with pytest.raises(ValueError, match="file_path"):
        loader.load_from_file(
            file_path="   ",
        )


def test_load_from_file_rejects_invalid_path_type():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    with pytest.raises(TypeError, match="file_path"):
        loader.load_from_file(
            file_path=object(),
        )


def test_loader_does_not_define_arbitrary_event_window():
    loader = CertifiedEconomicNewsSnapshotLoaderV2()

    forbidden = {
        "event_window",
        "window_minutes",
        "before_minutes",
        "after_minutes",
        "pre_event_window",
        "post_event_window",
    }

    assert forbidden.isdisjoint(vars(loader))
