"""Synthetic boundary witnesses; never substitute strategy evidence in research."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from unittest.mock import Mock

import pytest

from backend.backtesting.historical_eligibility_v31 import HistoricalEligibilityV31
from backend.backtesting.backtest_execution_simulator_v2 import BacktestExecutionSimulatorV2
from backend.tests.test_backtest_single_pass_v27b import build, Target, TradingActionV2
from backend.tests.test_production_certified_outcome_v17 import api_settings


@pytest.fixture
def policy():
    days = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()
    return HistoricalEligibilityV31({"timezone": "Central Standard Time", "sha256": "a"*64,
        "sessions": [{"BeginDay": days[(i-1) % 7], "BeginTime": "1700", "EndDay": days[i],
                      "EndTime": "1600", "TradingDay": days[i]} for i in range(5)],
        "full": {"2025-04-18": "synthetic full closure"},
        "partial": {"2025-05-26": {"type": "EARLY_CLOSE", "clock": "1200"}}})


def row(policy, stamp="20250619 150100", price=21805.25, contract="JUN25", number=1):
    return policy.observation(f"{stamp};{price};{price};{price};{price};5", contract=contract,
                              source_file="synthetic.txt", source_sha256="b"*64, source_row=number)


def simulate(policy, rows, contract="JUN25"):
    return BacktestExecutionSimulatorV2().simulate(symbol="NQ", direction="BUY", entry=21805.25,
        stop_loss=21775.25, take_profit=21865.25, contracts=1, risk_amount=600,
        candles=policy.eligible_candles(rows, contract=contract))


@pytest.mark.parametrize("price,reason", [(21775.25, "STOP_LOSS"), (21865.25, "TAKE_PROFIT")])
def test_eligible_normal_flat_candle_resolves_stop_and_profit(policy, price, reason):
    observed = row(policy, price=price)
    assert observed.source_observation_valid and observed.strategy_context_eligible
    assert observed.execution_price_eligible and observed.session_accounting_eligible
    assert simulate(policy, [observed]).reasoning[0] == reason


@pytest.mark.parametrize("stamp", ["20250619 213000", "20250622 155200", "20250620 133100",
                                  "20250526 173000", "20250418 150100"])
@pytest.mark.parametrize("price", [21775.25, 21865.25])
def test_anomalies_preserved_but_never_stop_profit_or_valuation(policy, stamp, price):
    observed = row(policy, stamp, price)
    assert observed.raw_row.startswith(stamp) and observed.source_observation_valid
    assert observed.source_row == 1 and observed.source_sha256 == "b"*64
    assert not any((observed.strategy_context_eligible, observed.execution_price_eligible,
                    observed.session_accounting_eligible))
    assert observed.trading_date is None and observed.anomaly_reasons
    trade = simulate(policy, [observed])
    assert trade.status == "NO_DATA" and trade.pnl == 0


def test_exact_sprint04_post_expiry_tp_witness_now_zero_completed(policy):
    anomalous = row(policy, "20250622 155200", 21865.25)
    assert anomalous.canonical_timestamp.isoformat() == "2025-06-22T10:51:00-05:00"
    assert simulate(policy, [anomalous]).status == "NO_DATA"
    prior = row(policy)
    censored = simulate(policy, [prior, anomalous])
    assert censored.reasoning[0] == "END_OF_DATA" and censored.pnl == 0


def test_cross_contract_prices_rejected_before_any_execution(policy):
    engine = Mock()
    with pytest.raises(ValueError, match="cross-contract"):
        policy.run_segment(engine, [row(policy), row(policy, contract="MAR25")], contract="JUN25")
    engine.run_single_pass.assert_not_called()


def test_same_contract_resume_and_lifecycle_marking_only_eligible(policy, api_settings):
    target = Target([{"accepted": True, "active_position_id": "test"}], close_at=21865.25)
    engine, session, strategy, executor = build(actions=[TradingActionV2.BUY], target=target)
    rows = [row(policy, "20250618 205900"), row(policy, "20250618 210100", 21865.25),
            row(policy, "20250618 220100"), row(policy, "20250618 220200", 21865.25)]
    result = policy.run_segment(engine, rows, contract="JUN25")
    assert len(session.candle_history) == 3 and len(strategy.contexts) == 2
    assert [c["signal_index"] for c in strategy.contexts] == [1, 2]
    assert result.trades[0].reasoning[0] == "TAKE_PROFIT"
    assert executor.simulator.simulate.call_args.kwargs["candles"][0].close == 21805.25
    assert all(c["timestamp"] != rows[1].canonical_timestamp for c in session.candle_history)
    assert len(target.updates) == 2  # neither marking nor completion on excluded row
    assert len(session.position_update_results) == 2


@pytest.mark.parametrize("accepted", [False, None, "true", 1])
def test_rejection_still_has_zero_execution(policy, api_settings, accepted):
    target = Target([{"accepted": accepted, "reason": "risk_veto"}])
    engine, session, strategy, executor = build(actions=[TradingActionV2.BUY], target=target)
    policy.run_segment(engine, [row(policy), row(policy, "20250619 150200")], contract="JUN25")
    assert len(target.calls) == 1 and session.simulated_trades == []
    executor.simulator.simulate.assert_not_called()


def test_htf_gap_and_future_perturbation_no_retroactive_context(policy, api_settings):
    # Explicit early-close at 12:07 clips a partial bucket; eligible 17:00
    # restart cannot fill that missing interval. Prior complete bars survive.
    policy.partial[datetime(2025, 6, 18).date()] = {"type": "EARLY_CLOSE", "clock": "1207"}
    start = datetime(2025, 6, 18, 16, 46)
    rows = [row(policy, (start+timedelta(minutes=i)).strftime("%Y%m%d %H%M%S")) for i in range(30)]
    rows += [row(policy, "20250618 220100"), row(policy, "20250618 220200")]
    runs = []
    for last in (21805.25, 22805.25):
        data = rows[:-1]+[row(policy, "20250618 220200", last)]
        engine, session, strategy, executor = build()
        policy.run_segment(engine, data, contract="JUN25")
        assert session.htf_aggregator.emitted_counts["15m"] == 1
        assert all(c["high"] == c["low"] for c in session.candle_history)
        assert all("future_candles" not in c for c in strategy.contexts)
        assert all(bar["timestamp"]+timedelta(minutes=15) <= c["decision_time"]
                   for c in strategy.contexts for bar in c["history_15m"])
        runs.append(strategy.contexts)
    assert runs[0] == runs[1]


def test_native_dst_instants_lineage_order_and_fail_closed(policy, tmp_path):
    lines = "20241103 065900;100;100;100;100;5\n20241103 070100;100;100;100;100;5\n"
    path = tmp_path/"native.txt"
    path.write_bytes(lines.encode())
    rows = policy.load_native(path, contract="DEC24", expected_sha256=sha256(path.read_bytes()).hexdigest())
    assert [r.canonical_timestamp.isoformat() for r in rows] == ["2024-11-03T01:58:00-05:00", "2024-11-03T01:00:00-06:00"]
    assert rows[0].candle().timestamp < rows[1].candle().timestamp
    assert all(r.available_at-r.canonical_timestamp.astimezone(timezone.utc) == timedelta(minutes=1) for r in rows)
    with pytest.raises(ValueError, match="backward"):
        policy.eligible_candles(rows[::-1], contract="DEC24")
    with pytest.raises(ValueError, match="authoritative"):
        policy.eligible_candles([replace(rows[0], execution_price_eligible=True)], contract="DEC24")
    with pytest.raises(ValueError, match="hash"):
        policy.load_native(path, contract="DEC24", expected_sha256="0"*64)


def test_terminal_ineligible_rows_do_not_create_last_candle_entry(policy, api_settings):
    engine, session, strategy, executor = build(actions=[TradingActionV2.BUY])
    policy.run_segment(engine, [row(policy), row(policy, "20250622 155200", 21865.25)], contract="JUN25")
    assert strategy.contexts == [] and session.simulated_trades == []
    executor.execute.assert_not_called()


def test_terminal_open_position_remains_unresolved_not_fake_profit(policy, api_settings):
    target = Target([{"accepted": True, "active_position_id": "old-contract"}], close_at=21865.25)
    engine, session, strategy, executor = build(actions=[TradingActionV2.BUY], target=target)
    result = policy.run_segment(engine, [row(policy), row(policy, "20250619 150200", 21806.25),
        row(policy, "20250622 155200", 21865.25)], contract="JUN25")
    assert session.active_position_id == "old-contract"
    assert target.updates == [("old-contract", 21806.25)]
    assert result.trades[0].reasoning[0] == "END_OF_DATA"
    assert result.trades[0].pnl == 20  # censored valuation, not realized completion
    assert all(t.reasoning[0] not in {"TAKE_PROFIT", "STOP_LOSS"} for t in result.trades)


def test_hold_and_standalone_behavior(policy, api_settings):
    data = [row(policy), row(policy, "20250619 150200", 21865.25)]
    target = Target([])
    engine, session, strategy, executor = build(target=target)
    policy.run_segment(engine, data, contract="JUN25")
    assert target.calls == [] and session.simulated_trades == []
    executor.execute.assert_not_called()
    engine, session, strategy, executor = build(actions=[TradingActionV2.BUY], signals=False)
    result = policy.run_segment(engine, data, contract="JUN25")
    assert result.trades[0].reasoning[0] == "TAKE_PROFIT"
