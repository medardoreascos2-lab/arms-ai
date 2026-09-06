from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.services.certified_economic_news_snapshot_v2 import (
    CertifiedEconomicNewsSnapshotV2,
)


def _provider_class():
    from backend.services.economic_news_runtime_provider_v2 import (
        EconomicNewsRuntimeProviderV2,
    )

    return EconomicNewsRuntimeProviderV2


def _timestamp(
    *,
    hour: int,
    minute: int = 0,
) -> datetime:
    return datetime(
        2026,
        9,
        8,
        hour,
        minute,
        tzinfo=timezone.utc,
    )


def _snapshot(
    *,
    events=(),
) -> CertifiedEconomicNewsSnapshotV2:
    return CertifiedEconomicNewsSnapshotV2(
        snapshot_version="test-v1",
        generated_at=_timestamp(hour=0),
        coverage_start=_timestamp(hour=0),
        coverage_end=_timestamp(hour=23, minute=59),
        high_impact_events=events,
    )


def test_provider_without_snapshot_reports_no_coverage():
    provider_cls = _provider_class()

    provider = provider_cls()

    assert (
        provider.is_timestamp_covered(
            timestamp=_timestamp(hour=12),
        )
        is False
    )


def test_provider_without_snapshot_returns_fail_closed_authority():
    provider_cls = _provider_class()

    provider = provider_cls()

    authority = provider.get_economic_news_authority()

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=_timestamp(hour=12),
        )
        is True
    )

    assert (
        authority.is_news_blocked(
            symbol="MNQ",
            timestamp=_timestamp(hour=12),
        )
        is True
    )


def test_provider_owns_exact_certified_snapshot():
    provider_cls = _provider_class()

    snapshot = _snapshot()

    provider = provider_cls(
        snapshot=snapshot,
    )

    assert provider.snapshot is snapshot


def test_provider_rejects_invalid_snapshot_type():
    provider_cls = _provider_class()

    with pytest.raises(TypeError):
        provider_cls(
            snapshot=object(),
        )


def test_provider_delegates_coverage_to_snapshot():
    provider_cls = _provider_class()

    snapshot = _snapshot()

    provider = provider_cls(
        snapshot=snapshot,
    )

    assert (
        provider.is_timestamp_covered(
            timestamp=_timestamp(hour=0),
        )
        is True
    )

    assert (
        provider.is_timestamp_covered(
            timestamp=_timestamp(hour=23, minute=59),
        )
        is True
    )

    assert (
        provider.is_timestamp_covered(
            timestamp=(
                _timestamp(hour=0)
                - timedelta(seconds=1)
            ),
        )
        is False
    )

    assert (
        provider.is_timestamp_covered(
            timestamp=(
                _timestamp(hour=23, minute=59)
                + timedelta(seconds=1)
            ),
        )
        is False
    )


def test_inside_coverage_without_event_is_allowed():
    provider_cls = _provider_class()

    provider = provider_cls(
        snapshot=_snapshot(),
    )

    authority = provider.get_economic_news_authority()

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=_timestamp(hour=12),
        )
        is False
    )


def test_inside_coverage_exact_high_impact_event_is_blocked():
    provider_cls = _provider_class()

    event = _timestamp(
        hour=14,
        minute=30,
    )

    provider = provider_cls(
        snapshot=_snapshot(
            events=(event,),
        ),
    )

    authority = provider.get_economic_news_authority()

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=event,
        )
        is True
    )


def test_outside_coverage_is_fail_closed_even_without_event():
    provider_cls = _provider_class()

    provider = provider_cls(
        snapshot=_snapshot(),
    )

    authority = provider.get_economic_news_authority()

    outside = (
        _timestamp(hour=23, minute=59)
        + timedelta(seconds=1)
    )

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=outside,
        )
        is True
    )


def test_unsupported_symbol_remains_fail_closed():
    provider_cls = _provider_class()

    provider = provider_cls(
        snapshot=_snapshot(),
    )

    authority = provider.get_economic_news_authority()

    assert (
        authority.is_news_blocked(
            symbol="ES",
            timestamp=_timestamp(hour=12),
        )
        is True
    )


def test_provider_does_not_create_arbitrary_event_window():
    provider_cls = _provider_class()

    event = _timestamp(
        hour=14,
        minute=30,
    )

    provider = provider_cls(
        snapshot=_snapshot(
            events=(event,),
        ),
    )

    authority = provider.get_economic_news_authority()

    before = event - timedelta(seconds=1)
    after = event + timedelta(seconds=1)

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=before,
        )
        is False
    )

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=event,
        )
        is True
    )

    assert (
        authority.is_news_blocked(
            symbol="NQ",
            timestamp=after,
        )
        is False
    )


def test_provider_returns_single_owned_authority_instance():
    provider_cls = _provider_class()

    provider = provider_cls(
        snapshot=_snapshot(),
    )

    first = provider.get_economic_news_authority()
    second = provider.get_economic_news_authority()

    assert first is second
