"""Certification provenance and synthetic aggregation geometry, not native replay.

The native witness stays private. Prices/volumes below are synthetic; only the
observed interval layout is reproduced. No runtime, broker or account is opened.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from backend.backtesting.closed_bar_aggregator_v1 import ClosedBarAggregatorV1
from backend.models.candle import Candle

ROOT = Path(__file__).resolve().parents[2]
CERT = ROOT / "backend/tests/market_open_native_certification_sprint13.json"
UTC = timezone.utc
MINUTE = timedelta(minutes=1)
FIRST_OPEN = datetime(2026, 9, 21, 0, 54, tzinfo=UTC)


def synthetic_minutes():
    return [Candle("NQ", "1m", 20000+i*.25, 20001+i*.25, 19999+i*.25,
                   20000.5+i*.25, i+1, FIRST_OPEN+i*MINUTE) for i in range(123)]


def test_observed_interval_geometry_emits_only_complete_buckets_and_exact_ohlcv():
    source = synthetic_minutes()
    agg = ClosedBarAggregatorV1()
    closes_15m = [datetime(2026, 9, 21, 1, tzinfo=UTC)+i*15*MINUTE for i in range(1, 8)]
    closes_1h = [datetime(2026, 9, 21, 2, tzinfo=UTC)]
    for candle in source:
        agg.update_completed(candle)
        available = candle.timestamp+MINUTE
        assert agg.emitted_counts == {
            "15m": sum(t <= available for t in closes_15m),
            "1h": sum(t <= available for t in closes_1h),
        }
    for tf, minutes in (("15m", 15), ("1h", 60)):
        for bar in agg.history(tf):
            start = bar.timestamp.astimezone(UTC)
            members = [c for c in source if start <= c.timestamp < start+minutes*MINUTE]
            assert len(members) == minutes
            assert (bar.open, bar.high, bar.low, bar.close, bar.volume) == (
                members[0].open, max(c.high for c in members), min(c.low for c in members),
                members[-1].close, sum(c.volume for c in members))
    assert [c.timestamp.astimezone(UTC) for c in agg.history("1h")] == [closes_1h[0]-60*MINUTE]


@pytest.mark.parametrize("missing_minute", [0, 7, 30, 59])
def test_one_missing_constituent_cannot_be_padded_into_a_certified_hour(missing_minute):
    omitted = datetime(2026, 9, 21, 1, missing_minute, tzinfo=UTC)
    agg = ClosedBarAggregatorV1()
    for candle in synthetic_minutes():
        if candle.timestamp != omitted:
            agg.update_completed(candle)
    assert agg.emitted_counts == {"15m": 6, "1h": 0}
    assert agg.history("1h") == []


def test_native_certificate_is_bound_to_reviewed_source_and_preserves_scope():
    evidence = json.loads(CERT.read_text(encoding="utf-8"))
    assert evidence["evidence_kind"] == "NATIVE_CURRENT"
    assert evidence["native_prefix_records"] == sum(evidence["frame_counts"].values())
    assert evidence["canonical_1m_count"] == evidence["frame_counts"]["CLOSED"]
    first = datetime.fromisoformat(evidence["candles"]["CLOSED"]["first_close_label"].replace("Z", "+00:00"))
    last = datetime.fromisoformat(evidence["candles"]["CLOSED"]["last_close_label"].replace("Z", "+00:00"))
    assert int((last-first)/MINUTE)+1 == evidence["canonical_1m_count"]
    for name, expected in evidence["reviewed_source_sha256"].items():
        # Sprint 13 certifies its original exporter, not later instrumentation.
        reviewed = ROOT/name
        if name == "integrations/ninjatrader/ArmsReadOnlyMarketV1.cs":
            reviewed = ROOT/"backend/tests/fixtures/ArmsReadOnlyMarketV1.sprint13.cs"
        assert sha256(reviewed.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == expected, name
    for tf, minutes in (("15m", 15), ("1h", 60)):
        detail = evidence["htf"][tf]
        assert detail["count"] == len(detail["complete_bucket_starts"])
        complete = set(detail["complete_bucket_starts"])
        for partial in detail["incomplete_buckets_not_emitted"]:
            assert 0 < partial["observations"] < minutes and partial["start"] not in complete
    plans = json.loads((ROOT/"backend/tests/native_test_plans_sprint13.json").read_text())["plans"]
    market, = [p for p in plans if p["purpose"] == "market_open"]
    assert market["certification_artifact"] == str(CERT.relative_to(ROOT)).replace("\\", "/")
    assert market["certified_session"] == evidence["session"]
    assert market["native_status"] == evidence["status"]
    assert all(p["native_status"] == "PENDING" for p in plans if p["purpose"] != "market_open")
    assert not evidence["readiness"]["read_only_sim_discovery"]
    assert not evidence["readiness"]["external_sim_account_test"]
    assert evidence["safety"]["sim_order_authority"] == "DISABLED"
    assert evidence["safety"]["live_authority"] is False
