import pytest

from backend.tests.research_fresh_validation_v31 import read, digest, EVIDENCE
from backend.tests.research_historical_accounting_sprint07r import OUT
from backend.tests.research_historical_realism_sprint07r import metrics


def test_certified_6984_counterfactual_has_direct_intrabar_closure_evidence():
    evidence=read(OUT/"JUN22_80_C0.json")
    witness=next(d for d in evidence["differences"] if d["index"]==6984)
    assert witness["legacy"]["reason"]=="ACTIVE POSITION"
    assert witness["canonical"]["reason"]=="Opposite CHOCH detected"
    assert witness["classification"]=="POSITION_FEEDBACK_EXPECTED"
    assert witness["counterfactual_matches"]
    assert witness["intrabar_close_indices"]==[6984]
    assert evidence["difference_counts"].get("UNEXPLAINED",0)==0
    assert evidence["account_pnl_matches_journal"] and evidence["result_pnl_matches_account"]


def test_cohort_metrics_keep_gross_fees_net_and_independent_drawdowns_separate():
    rows=[{"contract":"A","gross_pnl":-600,"fees":5,"net_pnl":-605},
          {"contract":"B","gross_pnl":-600,"fees":5,"net_pnl":-605}]
    result=metrics(rows)
    assert result["gross_pnl"]==-1200 and result["fees"]==10 and result["net_pnl"]==-1210
    assert result["max_independent_segment_realized_drawdown"]==605
    assert "max_drawdown" not in result
    assert result["completed_trades"]==2 and result["expectancy"]==-605
    assert result["max_contract_trade_share"]==.5
    assert result["max_positive_contract_pnl_share"] is None
    assert result["max_share_of_sum_independent_segment_realized_drawdowns"]==.5


def test_empty_cohort_does_not_fabricate_edge():
    result=metrics([])
    assert result["completed_trades"]==0
    assert result["expectancy"] is None and result["profit_factor"] is None


@pytest.mark.parametrize("contract,boundary", [
    (s["contract"],b) for s in read(EVIDENCE/"predeclared_experiment.json")["segments"] for b in (90,80,80.5)])
def test_completed_real_data_trades_reconcile_fills_daily_pnl_and_balance(contract,boundary):
    evidence=read(OUT/(contract+"_"+str(boundary).replace(".","_")+"_C0.json"))
    balance=evidence["account"]["starting_balance"]
    days={}; entries=set()
    for trade in evidence["trades"]:
        sign=1 if trade["direction"]=="LONG" else -1
        assert trade["gross_pnl"] == (trade["executed_exit"]-trade["executed_entry"])*sign*trade["quantity"]*trade["point_value"]
        assert trade["net_pnl"] == trade["gross_pnl"]-trade["fees"]
        assert trade["exit_index"]>trade["entry_index"]
        assert trade["entry_index"] not in entries
        entries.add(trade["entry_index"])
        balance+=trade["net_pnl"]
        day=trade["trading_date"]
        days[day]=days.get(day,0)+trade["net_pnl"]
        assert trade["balance_after"]==balance
        assert trade["daily_pnl_after"]==days[day]
    assert balance==evidence["account"]["balance"]
    assert evidence["completed_trades"]==evidence["journal_completed"]==len(entries)
    assert evidence["net_pnl"]==balance-evidence["account"]["starting_balance"]
    assert evidence["account_pnl_matches_journal"] and evidence["result_pnl_matches_account"]
    assert evidence["difference_counts"].get("UNEXPLAINED",0)==0
    assert all(d["counterfactual_matches"] and d["causal_roots"] for d in evidence["differences"])


def test_canonical_baselines_and_research_code_are_frozen_before_cost_replay():
    declaration=read(OUT/"cost_predeclaration.json")
    assert declaration["phase"]=="BEFORE_COST_REPLAYS"
    assert len(declaration["canonical_baseline_hashes"])==39
    assert all(digest(p)==h for p,h in declaration["canonical_baseline_hashes"].items())
    assert all(digest(p)==h for p,h in declaration["research_code_sha256"].items())
    assert digest("backend/backtesting/historical_accounting_v1.py")==declaration["execution_sha256"]


@pytest.mark.parametrize("contract,boundary,scenario", [
    (s["contract"],b,c) for s in read(EVIDENCE/"predeclared_experiment.json")["segments"]
    for b in (80,80.5) for c in read(OUT/"cost_predeclaration.json")["scenarios"]])
def test_every_cost_run_has_exact_adverse_fills_fees_and_one_account_realization(contract,boundary,scenario):
    evidence=read(OUT/(contract+"_"+str(boundary).replace(".","_")+"_"+scenario["name"]+".json"))
    slip=scenario["slippage_ticks_side"]*.25
    assert scenario["roundtrip_slippage_dollars_per_contract"]==slip*20*2
    balance=evidence["account"]["starting_balance"]
    days={};entries=set()
    for t in evidence["trades"]:
        sign=1 if t["direction"]=="LONG" else -1
        assert t["executed_entry"]==t["planned_entry"]+sign*slip
        assert t["executed_exit"]==t["trigger_price"]-sign*slip
        assert abs(t["planned_entry"]-t["stop"])==30
        assert abs(t["planned_entry"]-t["target"])==60
        assert t["gross_pnl"]==(t["executed_exit"]-t["executed_entry"])*sign*t["quantity"]*20
        assert t["fees"]==scenario["fee_per_contract_side"]*2*t["quantity"]
        assert t["net_pnl"]==t["gross_pnl"]-t["fees"]
        assert t["entry_index"] not in entries and t["exit_index"]>t["entry_index"]
        entries.add(t["entry_index"])
        balance+=t["net_pnl"]
        days[t["trading_date"]]=days.get(t["trading_date"],0)+t["net_pnl"]
        assert t["balance_after"]==balance and t["daily_pnl_after"]==days[t["trading_date"]]
    assert balance==evidence["account"]["balance"]
    assert evidence["completed_trades"]==evidence["journal_completed"]==len(entries)
    assert evidence["account_pnl_matches_journal"] and evidence["result_pnl_matches_account"]
