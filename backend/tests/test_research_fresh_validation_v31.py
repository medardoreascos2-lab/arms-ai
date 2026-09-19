from datetime import date, timedelta, timezone

from backend.tests.research_fresh_validation_v31 import certify_rollover, next_session, trade_metrics, aggregate, observe, submission_records
from backend.tests.test_historical_eligibility_v31 import policy, row
from backend.tests.research_calibration_v30 import factory, hypothetical_boundary, session_for
from backend.tests.diagnose_zero_signal_funnel_v28 import session_decisions
from backend.tests.test_production_certified_outcome_v17 import api_settings


def test_rollover_requires_two_completed_both_volume_leads_and_next_session(policy):
    old, new = {}, {}
    for day, av, bv in ((date(2025, 6, 9), 20, 10), (date(2025, 6, 10), 10, 20), (date(2025, 6, 11), 10, 20), (date(2025, 6, 12), 10, 20)):
        start, end = [d.astimezone(timezone.utc) for d in policy.session_bounds(day)]
        for stamp in (start, end-timedelta(minutes=1)):
            old[stamp], new[stamp] = av, bv
    result = certify_rollover(policy, old, new, "MAR25", "JUN25")
    assert result["certified"]
    assert [r["trading_date"] for r in result["confirmation"]] == ["2025-06-10", "2025-06-11"]
    assert result["boundary"] == policy.session_bounds(date(2025, 6, 12))[0]
    assert result["boundary"] > result["confirmation"][-1]["completed_at"]
    # Total-volume lead alone cannot certify if shared minutes lose.
    for stamp in list(new):
        new[stamp] = 1
        new[stamp-timedelta(minutes=1)] = 100
    assert not certify_rollover(policy, old, new, "MAR25", "JUN25")["certified"]


def test_next_valid_session_skips_full_holiday_and_weekend(policy):
    assert next_session(policy, date(2025, 4, 17)) == date(2025, 4, 21)


def test_compact_observer_transparent_to_real_strategy(policy, api_settings):
    candles = policy.eligible_candles([row(policy, f"20250619 15{i:02d}00", 21805.25+i*.25) for i in range(1, 31)], contract="JUN25")
    a, b = factory(), factory()
    with hypothetical_boundary(a, 80):
        observed, rows, traces = observe(a, candles)
    with hypothetical_boundary(b, 80):
        plain = b.run_single_pass(candles)
    assert session_decisions(a) == session_decisions(b)
    assert observed.trades == plain.trades
    assert observed.statistics == plain.statistics
    assert len(rows) == len(session_for(a).decisions)


def test_metrics_and_independent_aggregation_do_not_splice_drawdown():
    trades = [{"pnl": p, "completed": True, "date": "2025-01-01", "direction": "BUY", "regime": "TREND_UP", "session": "ETH"} for p in (1200, -600)]
    metric = trade_metrics(trades)
    assert metric["net_pnl"] == 600 and metric["profit_factor"] == 2 and metric["max_drawdown"] == 600
    segment = {**metric, "trades": trades, "a_plus_opportunities": 2, "clustering": {"episodes": 2}, "simulated_trades": 3,
               "censored_valuations": [{"pnl": 9999}], "terminal_unresolved_positions": 1}
    result = aggregate([segment, segment])
    assert result["net_pnl"] == 1200 and result["completed_trades"] == 4
    assert "max_drawdown" not in result
    assert result["max_segment_drawdown"] == 600
    assert result["censored_valuations"] == 2
    assert result["classification"] == "INSUFFICIENT_EVIDENCE"


def test_submission_counts_exclude_real_independent_outcome_records(policy, api_settings):
    from backend.tests.test_backtest_single_pass_v27b import build, Target, TradingActionV2
    target = Target([{"accepted": True}, {"accepted": False}])
    engine, session, strategy, executor = build(actions=[TradingActionV2.BUY]*2, target=target)
    policy.run_segment(engine, [row(policy), row(policy, "20250619 150200", 21865.25),
                               row(policy, "20250619 150300")], contract="JUN25")
    assert len(session.submission_results) == 3
    assert len(session.simulated_trades) == 1
    assert submission_records(session) == [{"accepted": True}, {"accepted": False}]
