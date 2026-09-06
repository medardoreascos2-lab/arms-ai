from datetime import datetime, timezone

import pytest


def _snapshot_class():
    from backend.services.certified_economic_news_snapshot_v2 import (
        CertifiedEconomicNewsSnapshotV2,
    )

    return CertifiedEconomicNewsSnapshotV2


def _utc(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
) -> datetime:
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=timezone.utc,
    )


def _build_snapshot(
    *,
    snapshot_version: str = "2026-09-06-v1",
    generated_at: datetime | None = None,
    coverage_start: datetime | None = None,
    coverage_end: datetime | None = None,
    high_impact_events=(),
):
    cls = _snapshot_class()

    return cls(
        snapshot_version=snapshot_version,
        generated_at=(
            generated_at
            if generated_at is not None
            else _utc(2026, 9, 5, 23, 0)
        ),
        coverage_start=(
            coverage_start
            if coverage_start is not None
            else _utc(2026, 9, 6, 0, 0)
        ),
        coverage_end=(
            coverage_end
            if coverage_end is not None
            else _utc(2026, 9, 6, 23, 59)
        ),
        high_impact_events=high_impact_events,
    )


def test_snapshot_exposes_certified_metadata_and_events():
    event = _utc(
        2026,
        9,
        6,
        14,
        30,
    )

    snapshot = _build_snapshot(
        high_impact_events=(event,),
    )

    assert snapshot.snapshot_version == "2026-09-06-v1"

    assert snapshot.generated_at == _utc(
        2026,
        9,
        5,
        23,
        0,
    )

    assert snapshot.coverage_start == _utc(
        2026,
        9,
        6,
        0,
        0,
    )

    assert snapshot.coverage_end == _utc(
        2026,
        9,
        6,
        23,
        59,
    )

    assert snapshot.high_impact_events == frozenset(
        {
            event,
        }
    )


def test_empty_event_set_is_valid_only_with_explicit_coverage():
    snapshot = _build_snapshot(
        high_impact_events=(),
    )

    assert snapshot.high_impact_events == frozenset()

    assert snapshot.is_timestamp_covered(
        timestamp=_utc(
            2026,
            9,
            6,
            12,
            0,
        )
    ) is True


def test_coverage_is_inclusive_at_both_boundaries():
    snapshot = _build_snapshot()

    assert snapshot.is_timestamp_covered(
        timestamp=snapshot.coverage_start,
    ) is True

    assert snapshot.is_timestamp_covered(
        timestamp=snapshot.coverage_end,
    ) is True


def test_timestamp_before_coverage_is_not_covered():
    snapshot = _build_snapshot()

    assert snapshot.is_timestamp_covered(
        timestamp=_utc(
            2026,
            9,
            5,
            23,
            59,
        )
    ) is False


def test_timestamp_after_coverage_is_not_covered():
    snapshot = _build_snapshot()

    assert snapshot.is_timestamp_covered(
        timestamp=_utc(
            2026,
            9,
            7,
            0,
            0,
        )
    ) is False


def test_rejects_blank_snapshot_version():
    with pytest.raises(
        ValueError,
        match="snapshot_version",
    ):
        _build_snapshot(
            snapshot_version="   ",
        )


def test_rejects_naive_generated_at():
    with pytest.raises(
        ValueError,
        match="generated_at",
    ):
        _build_snapshot(
            generated_at=datetime(
                2026,
                9,
                5,
                23,
                0,
            ),
        )


def test_rejects_naive_coverage_start():
    with pytest.raises(
        ValueError,
        match="coverage_start",
    ):
        _build_snapshot(
            coverage_start=datetime(
                2026,
                9,
                6,
                0,
                0,
            ),
        )


def test_rejects_naive_coverage_end():
    with pytest.raises(
        ValueError,
        match="coverage_end",
    ):
        _build_snapshot(
            coverage_end=datetime(
                2026,
                9,
                6,
                23,
                59,
            ),
        )


def test_rejects_inverted_coverage_range():
    with pytest.raises(
        ValueError,
        match="coverage",
    ):
        _build_snapshot(
            coverage_start=_utc(
                2026,
                9,
                7,
                0,
                0,
            ),
            coverage_end=_utc(
                2026,
                9,
                6,
                0,
                0,
            ),
        )


def test_rejects_naive_high_impact_event():
    with pytest.raises(
        ValueError,
        match="high_impact",
    ):
        _build_snapshot(
            high_impact_events=(
                datetime(
                    2026,
                    9,
                    6,
                    14,
                    30,
                ),
            ),
        )


def test_rejects_high_impact_event_before_coverage():
    with pytest.raises(
        ValueError,
        match="coverage",
    ):
        _build_snapshot(
            high_impact_events=(
                _utc(
                    2026,
                    9,
                    5,
                    23,
                    59,
                ),
            ),
        )


def test_rejects_high_impact_event_after_coverage():
    with pytest.raises(
        ValueError,
        match="coverage",
    ):
        _build_snapshot(
            high_impact_events=(
                _utc(
                    2026,
                    9,
                    7,
                    0,
                    0,
                ),
            ),
        )


def test_timestamp_coverage_requires_datetime():
    snapshot = _build_snapshot()

    with pytest.raises(
        TypeError,
        match="timestamp",
    ):
        snapshot.is_timestamp_covered(
            timestamp="2026-09-06T12:00:00Z",
        )


def test_timestamp_coverage_rejects_naive_datetime():
    snapshot = _build_snapshot()

    with pytest.raises(
        ValueError,
        match="timestamp",
    ):
        snapshot.is_timestamp_covered(
            timestamp=datetime(
                2026,
                9,
                6,
                12,
                0,
            ),
        )


def test_snapshot_does_not_define_arbitrary_news_window():
    snapshot = _build_snapshot(
        high_impact_events=(
            _utc(
                2026,
                9,
                6,
                14,
                30,
            ),
        ),
    )

    assert not hasattr(
        snapshot,
        "window_minutes",
    )

    assert not hasattr(
        snapshot,
        "pre_event_minutes",
    )

    assert not hasattr(
        snapshot,
        "post_event_minutes",
    )
