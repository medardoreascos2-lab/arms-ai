from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.backtesting.closed_bar_aggregator_v1 import ClosedBarAggregatorV1, chicago_open
from backend.models.candle import Candle
from backend.tests.test_backtest_single_pass_v27b import build
from backend.tests.test_production_certified_outcome_v17 import api_settings


def minutes(count, start=datetime(2026, 8, 3, 9)):
    return [Candle("NQ", "1m", 20000+i, 20002+i, 19999+i, 20001+i, i+1,
                   start+timedelta(minutes=i)) for i in range(count)]


@pytest.mark.parametrize("period,tf,start", [(15, "15m", datetime(2026,8,3,9,30)),
                                            (60, "1h", datetime(2026,8,3,9))])
def test_exact_completion_boundary_and_ohlcv(period, tf, start):
    data = minutes(period+1, start)
    originals = [asdict(c) for c in data]
    agg = ClosedBarAggregatorV1()
    for candle in data[:period-1]:
        agg.update_completed(candle)
    assert agg.history(tf) == []
    assert agg.available_at == chicago_open(start + timedelta(minutes=period-1))
    agg.update_completed(data[period-1])
    bar, = agg.history(tf)
    assert asdict(bar) == asdict(Candle("NQ", tf, data[0].open,
        max(c.high for c in data[:period]), min(c.low for c in data[:period]),
        data[period-1].close, sum(c.volume for c in data[:period]), chicago_open(start)))
    assert agg.available_at == chicago_open(start + timedelta(minutes=period))
    agg.update_completed(data[period])
    assert agg.history(tf) == [bar]
    assert [asdict(c) for c in data] == originals


@pytest.mark.parametrize("period,tf", [(15,"15m"), (60,"1h")])
def test_missing_minute_partial_start_end_and_next_bucket(period, tf):
    data = minutes(period*3)
    for omit in ({7}, {0}, set(range(period-2, period))):
        agg = ClosedBarAggregatorV1()
        for i, candle in enumerate(data):
            if i not in omit:
                agg.update_completed(candle)
        assert agg.emitted_counts[tf] == 2
        assert agg.history(tf)[0].timestamp == chicago_open(data[period].timestamp)
    agg = ClosedBarAggregatorV1()
    for candle in data[:-1]:
        agg.update_completed(candle)
    assert agg.emitted_counts[tf] == 2  # No partial final flush.


def test_break_does_not_bridge_and_flat_minutes_are_preserved():
    data = minutes(60, datetime(2026,8,3,15)) + minutes(60, datetime(2026,8,3,17))
    data = [replace(c, open=20000, high=20000, low=20000, close=20000) for c in data]
    before = [asdict(c) for c in data]
    agg = ClosedBarAggregatorV1()
    for c in data:
        agg.update_completed(c)
    assert agg.emitted_counts == {"15m": 8, "1h": 2}
    assert [c.timestamp.hour for c in agg.history("1h")] == [15,17]
    assert all(c.open == c.high == c.low == c.close == 20000 for c in agg.history("1h"))
    assert sum(c.volume for c in agg.history("1h")) == sum(c.volume for c in data)
    assert [asdict(c) for c in data] == before


def test_future_and_in_progress_perturbations_do_not_change_visible_bars():
    original = minutes(121)
    changed = [replace(c, high=c.high+999, volume=c.volume+999) if i>=70 else c
               for i,c in enumerate(original)]
    left, right = ClosedBarAggregatorV1(history_limit=2), ClosedBarAggregatorV1(history_limit=2)
    for i, (a,b) in enumerate(zip(original,changed)):
        left.update_completed(a)
        right.update_completed(b)
        if i < 74:
            assert left.history("15m") == right.history("15m")
        if i < 119:
            assert left.history("1h") == right.history("1h")
        assert len(left.history("15m")) <= 2
    assert left.history("15m") != right.history("15m")
    assert left.history("1h") != right.history("1h")
    snapshot = left.history("1h")
    snapshot[-1].close = -1
    assert left.history("1h")[-1].close != -1


def test_chicago_naive_and_aware_inputs_agree():
    naive, aware = ClosedBarAggregatorV1(), ClosedBarAggregatorV1()
    for candle in minutes(60):
        naive.update_completed(candle)
        aware.update_completed(replace(candle, timestamp=chicago_open(candle.timestamp).astimezone(timezone.utc)))
    assert naive.history("1h") == aware.history("1h")
    assert naive.history("1h")[0].timestamp.utcoffset() == timedelta(hours=-5)


@pytest.mark.parametrize("timestamp", [datetime(2026,3,8,2,30), datetime(2026,11,1,1,30)])
def test_naive_dst_ambiguity_fails_closed(timestamp):
    with pytest.raises(ValueError, match="ambiguous or nonexistent"):
        chicago_open(timestamp)


def test_aware_dst_fold_is_two_distinct_complete_hours():
    agg = ClosedBarAggregatorV1()
    data = minutes(120, datetime(2026,11,1,6,tzinfo=timezone.utc))
    for candle in data:
        agg.update_completed(candle)
    bars = agg.history("1h")
    assert len(bars) == 2
    assert [c.timestamp.hour for c in bars] == [1,1]
    assert [c.timestamp.fold for c in bars] == [0,1]
    assert bars[0].timestamp.astimezone(timezone.utc) < bars[1].timestamp.astimezone(timezone.utc)


def test_aware_spring_transition_emits_no_nonexistent_hour():
    agg = ClosedBarAggregatorV1()
    for candle in minutes(120, datetime(2026,3,8,7,tzinfo=timezone.utc)):
        agg.update_completed(candle)
    assert [c.timestamp.hour for c in agg.history("1h")] == [1,3]
    assert agg.emitted_counts == {"15m": 8, "1h": 2}


@pytest.mark.parametrize("kind", ["duplicate", "backward", "off_minute", "symbol", "timeframe"])
def test_invalid_source_contract_rejected(kind):
    agg = ClosedBarAggregatorV1()
    first, second = minutes(2)
    agg.update_completed(first)
    bad = {"duplicate": first, "backward": replace(first, timestamp=first.timestamp-timedelta(minutes=1)),
           "off_minute": replace(second, timestamp=second.timestamp+timedelta(seconds=1)),
           "symbol": replace(second,symbol="ES"), "timeframe": replace(second,timeframe="5m")}[kind]
    with pytest.raises(ValueError):
        agg.update_completed(bad)


def test_single_pass_context_visibility_and_separate_bounded_histories(api_settings):
    engine, session, strategy, _ = build(window=4)
    data = minutes(181)
    engine.run_single_pass(data)
    assert len(session.candle_history) == 181
    assert len(strategy.contexts) == 180
    for i, context in enumerate(strategy.contexts):
        assert context["history"] is not context["history_15m"]
        assert context["history_15m"] is not context["history_1h"]
        assert context["history"] is not context["history_1h"]
        for key, tf, period in (("history_15m","15m",15),("history_1h","1h",60)):
            assert len(context[key]) == min(4,(i+1)//period)
            assert all(c["timeframe"] == tf for c in context[key])
            assert all(c["timestamp"]+timedelta(minutes=period) <= context["decision_time"] for c in context[key])
        assert all(c["timeframe"] == "1m" for c in context["history"])
    assert strategy.contexts[59]["history"] != strategy.contexts[59]["history_15m"]
    assert strategy.contexts[59]["history_15m"] != strategy.contexts[59]["history_1h"]


def test_strategy_htf_evidence_excludes_in_progress_changes(api_settings):
    data = minutes(121)
    perturbed = [replace(c, high=c.high+999) if i>=70 else c for i,c in enumerate(data)]
    left, _, left_strategy, _ = build()
    right, _, right_strategy, _ = build()
    left.run_single_pass(data)
    right.run_single_pass(perturbed)
    for i,(a,b) in enumerate(zip(left_strategy.contexts,right_strategy.contexts)):
        if i < 74:
            assert a["history_15m"] == b["history_15m"]
        if i < 119:
            assert a["history_1h"] == b["history_1h"]
    assert left_strategy.contexts[70]["history"] != right_strategy.contexts[70]["history"]
    assert left_strategy.contexts[74]["history_15m"] != right_strategy.contexts[74]["history_15m"]
    assert left_strategy.contexts[119]["history_1h"] != right_strategy.contexts[119]["history_1h"]
