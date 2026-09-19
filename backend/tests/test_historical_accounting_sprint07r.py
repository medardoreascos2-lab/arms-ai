"""Deterministic synthetic execution witnesses; no research score injection."""
from dataclasses import replace
from unittest.mock import Mock

import pytest

from backend.backtesting.historical_accounting_v1 import HistoricalAccountingV1, HistoricalCostsV1
from backend.strategies.trading_strategy_v2 import TradingDecisionV2, TradingActionV2
from backend.tests.research_calibration_v30 import factory, session_for
from backend.tests.test_historical_eligibility_v31 import policy
from backend.tests.test_production_certified_outcome_v17 import api_settings


def observations(policy, prices=None, stamps=None):
    prices = prices or [(10000, 10000, 10000, 10000)] * 8
    stamps = stamps or [f"20250619 15{i:02d}00" for i in range(1, len(prices)+1)]
    return [policy.observation(f"{t};{o};{h};{l};{c};10", contract="JUN25",
            source_file="synthetic.txt", source_sha256="b"*64, source_row=i)
            for i, (t, (o,h,l,c)) in enumerate(zip(stamps, prices), 1)]


def build(policy, rows=None, *, action="BUY", costs=None, entries=(5,)):
    engine = factory()
    old = session_for(engine)
    old.trade_executor_v2.execute = Mock(side_effect=AssertionError("independent execution forbidden"))
    contexts = []
    def strategy(context):
        contexts.append({"index": context["signal_index"], "active": context["has_active_position"],
                         "history": list(context["history"])})
        if context["signal_index"] not in entries:
            return TradingDecisionV2(TradingActionV2.HOLD, .5, "fixture HOLD")
        price = context["candle"]["close"]
        sign = 1 if action == "BUY" else -1
        return TradingDecisionV2(TradingActionV2[action], .95, "synthetic execution witness",
            {"stop_loss": price-sign*30, "take_profit": price+sign*60,
             "confluence_score": .95, "grade": "A+", "reasons": []})
    old.strategy_runner_v2.run = strategy
    runtime = HistoricalAccountingV1(engine, policy=policy, observations=rows or observations(policy),
        contract="JUN25", costs=costs, strategy_version="synthetic-safety-witness")
    return runtime, contexts, old.trade_executor_v2.execute


@pytest.mark.parametrize("action,high,low,reason,pnl", [
    ("BUY",10001,9969,"STOP_LOSS",-600), ("SELL",10031,9999,"STOP_LOSS",-600),
    ("BUY",10061,9999,"TAKE_PROFIT",1200), ("SELL",10001,9939,"TAKE_PROFIT",1200),
    ("BUY",10061,9969,"STOP_LOSS",-600), ("SELL",10031,9939,"STOP_LOSS",-600)])
def test_intrabar_single_realization_updates_every_projection(policy, api_settings, action, high, low, reason, pnl):
    prices = [(10000,10000,10000,10000)]*8
    prices[5] = (10000,high,low,10000)
    r, contexts, independent = build(policy, observations(policy, prices), action=action)
    result = r.run()
    assert len(result.trades) == len(r.completed) == len(r.journal.get_closed_trades()) == 1
    assert len(r.lifecycle.get_trade_history()) == len(r.portfolio.get_closed_positions()) == 1
    assert len(r.lifecycle.broker_connector_v2.get_fills()) == 1
    assert result.trades[0].pnl == r.journal.trades[0].pnl == pnl
    assert r.completed[0]["exit_trigger"] == reason
    s = r.account.get_state()
    assert s["balance"] == s["equity"] == 150000+pnl
    assert s["daily_pnl"] == s["realized_pnl"] == pnl
    assert s["drawdown"] == max(0,-pnl)
    assert not next(c for c in contexts if c["index"] == 6)["active"]
    assert r.journal.trades[0].closed_at == r.rows[5].available_at
    assert r.journal.trades[0].historical == r.completed[0]
    independent.assert_not_called()
    before = r.account.capture_state()
    with pytest.raises(RuntimeError, match="duplicate"):
        r.record_close(r.session.position_update_results[0]["position"])
    assert r.account.capture_state() == before


def test_next_risk_reads_loss_balance_daily_and_drawdown(policy, api_settings):
    prices = [(10000,10000,10000,10000)]*9
    prices[5] = (10000,10000,9970,10000)
    r, _, _ = build(policy, observations(policy, prices), entries=(5,7))
    r.run()
    evaluations = [x for x in r.risk_evaluations if x["index"] == 7]
    assert evaluations
    assert all(x["inputs"]["account_balance"] == 149400 and x["inputs"]["daily_pnl"] == -600
               and x["inputs"]["total_drawdown"] == 600 for x in evaluations)


def test_next_risk_reads_profit_and_updated_peak(policy, api_settings):
    prices = [(10000,10000,10000,10000)]*9
    prices[5] = (10000,10060,10000,10000)
    r, _, _ = build(policy, observations(policy, prices), entries=(5,7))
    r.run()
    evaluations = [x for x in r.risk_evaluations if x["index"] == 7]
    assert evaluations
    assert all(x["inputs"]["account_balance"] == 151200 and x["inputs"]["daily_pnl"] == 1200
               and x["inputs"]["total_drawdown"] == 0 for x in evaluations)
    assert r.account.get_state()["peak_equity"] == 151200


def test_entry_bar_extremes_cannot_retrospectively_resolve_new_position(policy, api_settings):
    prices = [(10000,10000,10000,10000)]*8
    prices[4] = (10000,10100,9900,10000)
    r, _, independent = build(policy, observations(policy, prices))
    r.run()
    assert not r.completed and not r.journal.get_closed_trades()
    assert len(r.lifecycle.get_active_positions()) == 1
    assert r.account.get_state()["realized_pnl"] == 0
    independent.assert_not_called()


def test_daily_reset_is_historical_and_preserves_cumulative_pnl(policy, api_settings):
    stamps = [f"20250618 20{i:02d}00" for i in range(54,60)] + ["20250618 220100","20250618 220200"]
    prices = [(10000,10000,10000,10000)]*8
    prices[5] = (10000,10000,9970,10000)
    r, _, _ = build(policy, observations(policy, prices, stamps))
    r.run()
    assert r.completed[0]["daily_pnl_after"] == -600
    assert r.account.get_state()["daily_pnl"] == 0
    assert r.account.get_state()["realized_pnl"] == -600
    assert r.account.get_state()["trading_day"] == "2025-06-19"


def test_rejected_submission_and_hold_cannot_execute(policy, api_settings):
    r, _, _ = build(policy)
    r.lifecycle.execution_risk_gate_v1.evaluate_trade = Mock(return_value={"execution":"BLOCKED"})
    before = r.account.capture_state()
    r.run()
    assert r.session.submission_results[0]["accepted"] is False
    assert r.account.capture_state() == before
    assert not r.journal.trades and not r.completed and not r.lifecycle.broker_connector_v2.get_fills()
    hold, _, _ = build(policy, entries=())
    before = hold.account.capture_state()
    hold.run()
    assert hold.account.capture_state() == before


def test_anomaly_cannot_close_and_terminal_position_is_unrealized(policy, api_settings):
    stamps = [f"20250618 20{i:02d}00" for i in range(54,59)] + ["20250618 213000","20250618 220100"]
    prices = [(10000,10000,10000,10000)]*7
    prices[5] = (9900,9900,9900,9900)
    prices[6] = (9999,9999,9999,9999)
    r, _, _ = build(policy, observations(policy, prices, stamps))
    result = r.run()
    assert len(r.rows) == 6
    assert not result.trades and not r.completed
    assert len(r.lifecycle.get_active_positions()) == len(r.journal.get_open_trades()) == 1
    assert r.account.get_state()["realized_pnl"] == 0
    assert r.account.get_state()["unrealized_pnl"] == -20


def test_cross_contract_rejected_before_composition_mutation(policy, api_settings):
    engine = factory(); old = session_for(engine)
    rows = observations(policy)
    rows[-1] = replace(rows[-1], contract="MAR25")
    with pytest.raises(ValueError, match="cross-contract"):
        HistoricalAccountingV1(engine,policy=policy,observations=rows,contract="JUN25",strategy_version="test")
    assert session_for(engine) is old and old.signal_submission_target_v2.portfolio_manager_v2 is None


def test_flat_stop_and_cost_accounting_exact(policy, api_settings):
    prices = [(10000,10000,10000,10000)]*8
    prices[5] = (9970,9970,9970,9970)
    r, _, _ = build(policy,observations(policy,prices),costs=HistoricalCostsV1(2.5,1))
    r.run(); t=r.completed[0]
    assert t["executed_entry"] == 10000.25 and t["executed_exit"] == 9969.75
    assert t["stop"] == 9970 and t["target"] == 10060
    assert t["gross_pnl"] == -610 and t["fees"] == 5 and t["net_pnl"] == -615
    assert t["balance_after"] == 149385


def test_future_changes_do_not_change_prior_context_and_fresh_account(policy, api_settings):
    a, ac, _ = build(policy)
    prices = [(10000,10000,10000,10000)]*8
    prices[6] = (10000,10100,9900,10000)
    b, bc, _ = build(policy,observations(policy,prices))
    a.run();b.run()
    assert ac[:2] == bc[:2]
    assert not a.completed and len(b.completed)==1
    fresh, _, _ = build(policy)
    assert fresh.account.get_state()["balance"] == 150000
    assert fresh.account.get_state()["realized_pnl"] == 0
    with pytest.raises(RuntimeError, match="fresh"):
        b.run()


def test_accumulated_loss_activates_existing_projected_drawdown_veto(policy, api_settings):
    prices=[(10000+i,10000+i,10000+i,10000+i) for i in range(22)]
    entries=tuple(range(5,21,2))
    for i in entries:
        price=prices[i-1][3]
        prices[i]=(price,price,price-30,price)
    r, _, _ = build(policy,observations(policy,prices),entries=entries)
    r.run()
    assert len(r.completed)==7
    assert r.account.get_state()["realized_pnl"] == -4200
    veto=[x for x in r.risk_evaluations if x["index"]==19]
    assert veto and not veto[0]["approved"]
    assert "projected_total_drawdown_exceeded" in veto[0]["reasons"]
    assert len(r.lifecycle.broker_connector_v2.get_fills())==7


@pytest.mark.parametrize("acceptance", [False,None,"true",1])
def test_malformed_acceptance_never_reaches_independent_executor(policy, api_settings, acceptance):
    r, _, independent=build(policy)
    r.lifecycle.submit_signal=Mock(return_value={"accepted":acceptance})
    before=r.account.capture_state()
    r.run()
    assert not r.completed and not r.journal.trades and r.account.capture_state()==before
    independent.assert_not_called()


def test_feedback_classification_requires_matching_counterfactual_and_causal_root():
    from backend.tests.research_historical_accounting_sprint07r import classify_difference
    assert classify_difference(legacy="old",canonical="new",counterfactual="old",roots={"POSITION_FEEDBACK_EXPECTED"}) == "POSITION_FEEDBACK_EXPECTED"
    assert classify_difference(legacy="old",canonical="new",counterfactual="old",roots={"RISK_FEEDBACK_EXPECTED"}) == "RISK_FEEDBACK_EXPECTED"
    assert classify_difference(legacy="old",canonical="new",counterfactual="old",roots=set()) == "UNEXPLAINED"
    assert classify_difference(legacy="old",canonical="new",counterfactual="different",roots={"POSITION_FEEDBACK_EXPECTED"}) == "UNEXPLAINED"
