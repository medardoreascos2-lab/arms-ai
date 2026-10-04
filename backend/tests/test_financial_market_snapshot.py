"""F100C: fail-closed market data snapshots."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.financial.market_snapshot import MarketSnapshot, SnapshotState


NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def test_quote_freshness_requires_both_sides_and_valid_time():
    fresh = MarketSnapshot("NASDAQ:TEST", "synthetic:test", NOW,
                           bid=Decimal("10"), ask=Decimal("10.1"))
    assert fresh.freshness(NOW, timedelta(seconds=30)) is SnapshotState.FRESH
    assert fresh.freshness(NOW + timedelta(seconds=31), timedelta(seconds=30)) is SnapshotState.STALE
    assert fresh.freshness(NOW - timedelta(microseconds=1), timedelta(seconds=30)) is SnapshotState.FUTURE
    incomplete = MarketSnapshot("NASDAQ:TEST", "synthetic:test", NOW, last=Decimal("10"))
    assert incomplete.freshness(NOW, timedelta(seconds=30)) is SnapshotState.INCOMPLETE


def test_invalid_or_untrusted_quote_values_rejected():
    for fields in (
        {"bid": Decimal("10"), "ask": Decimal("9")},
        {"bid": Decimal("NaN")},
        {"last": Decimal("-1")},
        {"volume": Decimal("Infinity")},
    ):
        with pytest.raises(ValueError):
            MarketSnapshot("NASDAQ:TEST", "synthetic:test", NOW, **fields)
    with pytest.raises(ValueError, match="timezone-aware"):
        MarketSnapshot("NASDAQ:TEST", "synthetic:test", NOW.replace(tzinfo=None))


def test_depth_metadata_is_snapshot_copy():
    original = {"levels": "10"}
    snapshot = MarketSnapshot("NASDAQ:TEST", "synthetic:test", NOW, depth_metadata=original)
    original["levels"] = "0"
    assert snapshot.depth_metadata["levels"] == "10"
    with pytest.raises(TypeError):
        snapshot.depth_metadata["levels"] = "0"
