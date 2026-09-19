"""Offline canonical accounting evidence. Frozen V30/V31 are read-only inputs."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter, defaultdict
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
from unittest.mock import patch

from backend.backtesting.historical_accounting_v1 import HistoricalAccountingV1, HistoricalCostsV1
from backend.backtesting.historical_eligibility_v31 import HistoricalEligibilityV31, CHICAGO, MINUTE
from backend.tests.research_calibration_v30 import factory, session_for, hypothetical_boundary
from backend.tests.research_fresh_validation_v31 import EVIDENCE, read, write, load_segment, trade_metrics

OUT = Path("backend/tests/research_sprint07r")


def decision_value(d):
    return {**asdict(d), "action": d.action.value}


def run_legacy(candles, boundary):
    engine=factory(); session=session_for(engine); strategy=session.strategy_runner_v2
    records=[]; entries={}; current={}
    original=strategy.run; submit=session.signal_submission_target_v2.submit_signal
    def submitted(**kwargs):
        result=submit(**kwargs)
        if result.get("accepted") is True:
            entries[result["active_position_id"]]=current["index"]
        return result
    def observed(context):
        current["index"]=context["signal_index"]
        record={"index":current["index"], "active":context["has_active_position"],
                "active_entry":entries.get(context["active_position_id"]),
                "controller":deepcopy(strategy.signal_controller.__dict__),
                "position_state":strategy.position_state,
                "position_lifecycle":deepcopy(strategy.position_lifecycle.__dict__)}
        d=original(context);record["decision"]=decision_value(d); records.append(record)
        return d
    with hypothetical_boundary(engine,boundary),patch.object(strategy,"run",observed),patch.object(session.signal_submission_target_v2,"submit_signal",submitted):
        result=engine.run_single_pass(candles)
    return records, {"simulator_pnl":sum(t.pnl for t in result.trades),
                     "lifecycle_pnl":sum(t["realized_pnl"] for t in session.signal_submission_target_v2.get_trade_history()),
                     "trades":len(result.trades)}


def classify_difference(*, legacy, canonical, counterfactual, roots):
    """An unchanged strategy must reproduce the legacy decision when its
    position input and controller state are restored. Roots are explicit prior
    execution/risk events, never merely 'a difference happened earlier'.
    """
    if canonical == legacy:
        return None
    if counterfactual != legacy or not roots:
        return "UNEXPLAINED"
    return "RISK_FEEDBACK_EXPECTED" if "RISK_FEEDBACK_EXPECTED" in roots else "POSITION_FEEDBACK_EXPECTED"


def replay(contract, boundary, costs=None, compare=True):
    declaration=read(EVIDENCE/"predeclared_experiment.json")
    segment=next(s for s in declaration["segments"] if s["contract"]==contract)
    policy=HistoricalEligibilityV31(declaration["calendar"])
    observations=load_segment(policy,segment)
    candles=policy.eligible_candles(observations,contract=contract)
    baseline,legacy_metrics=run_legacy(candles,boundary) if compare else (None,None)
    if compare:
        frozen=read(EVIDENCE/(contract+"_"+str(boundary).replace(".","_")+".json"))
        assert legacy_metrics["simulator_pnl"] == frozen["net_pnl"]
        assert legacy_metrics["trades"] == frozen["completed_trades"]
    engine=factory()
    runtime=HistoricalAccountingV1(engine,policy=policy,observations=observations,contract=contract,
        costs=costs, strategy_version=f"ParameterizedStrategyRunnerV2/EMA10/SL30/TP60/quality85/research-{boundary}")
    session=runtime.session;strategy=session.strategy_runner_v2;original=strategy.run
    differences=[]; causal_decisions={}; entry_roots={}; metadata={}; current={}; opportunities=[]
    def observed(context):
        index=context["signal_index"];current.clear()
        before=deepcopy(strategy.signal_controller.__dict__)
        state_before=strategy.position_state
        lifecycle_before=deepcopy(strategy.position_lifecycle.__dict__)
        d=original(context); actual=decision_value(d)
        local=context["candle"]["timestamp"].astimezone(CHICAGO)
        history=context["history"]
        volatility=sum(c["high"]-c["low"] for c in history)/len(history)
        metadata[index]={"regime":current.get("regime",{}).get("regime","NOT_EVALUATED"),
                         "session":"RTH_0830_1500_CT" if (8,30)<=(local.hour,local.minute)<(15,0) else "ETH_OTHER",
                         "volatility_points":volatility, "year":local.year}
        confluence=current.get("confluence",{})
        if confluence.get("approved") and confluence.get("grade")=="A+" and current.get("quality",{}).get("approved"):
            opportunities.append(index)
        if baseline is not None:
            old=baseline[index-engine.minimum_candles]
            assert old["index"]==index
            roots=set()
            old_entry=old["active_entry"]
            active_entry=runtime.entries.get(context["active_position_id"],{}).get("entry_index")
            # Direct closure witness of the SAME previously accepted trade.
            closes=[t for t in runtime.completed if t["entry_index"]==old_entry and t["exit_index"]<=index]
            if old["active"] and not context["has_active_position"] and closes:
                roots.add("POSITION_FEEDBACK_EXPECTED")
            # An old accepted entry was vetoed by the corrected account state.
            if old["active"] and old_entry and any(r["index"]==old_entry and not r["approved"] for r in runtime.risk_evaluations):
                roots.add("RISK_FEEDBACK_EXPECTED")
            # Trace differences in active entries and cooldown state to their
            # earlier explained strategy decision or corrected risk rejection.
            for origin in (old_entry, active_entry, before.get("last_trade_index"), old["controller"].get("last_trade_index")):
                if origin in causal_decisions: roots.add(causal_decisions[origin])
                roots.update(entry_roots.get(origin,set()))
            if actual != old["decision"]:
                shadow=deepcopy(strategy)
                shadow.signal_controller.__dict__.update(old["controller"])
                shadow.position_state=old["position_state"]
                shadow.position_lifecycle.__dict__.update(old["position_lifecycle"])
                shadow_context=dict(context,has_active_position=old["active"],active_position_id="legacy" if old["active"] else None)
                counter=decision_value(type(strategy).run(shadow,shadow_context))
                classification=classify_difference(legacy=old["decision"],canonical=actual,counterfactual=counter,roots=roots)
                differences.append({"index":index,"time":context["decision_time"].isoformat(),
                    "legacy":old["decision"],"canonical":actual,"classification":classification,
                    "causal_roots":sorted(roots),"legacy_active_entry":old_entry,"canonical_active_entry":active_entry,
                    "intrabar_close_indices":[t["exit_index"] for t in closes],"counterfactual_matches":counter==old["decision"]})
                if classification=="UNEXPLAINED":
                    raise RuntimeError("UNEXPLAINED strategy difference: "+json.dumps(differences[-1]))
                causal_decisions[index]=classification
            if old["active"] != context["has_active_position"] and roots:
                entry_roots[index]=roots
            assert state_before==old["position_state"] and lifecycle_before==old["position_lifecycle"]
        return d
    def wrap(stack,owner,name,key):
        method=getattr(owner,name)
        def wrapped(*args,**kwargs):
            result=method(*args,**kwargs);current[key]=asdict(result) if hasattr(result,"__dataclass_fields__") else result
            return result
        stack.enter_context(patch.object(owner,name,wrapped))
    with ExitStack() as stack:
        stack.enter_context(hypothetical_boundary(engine,boundary))
        stack.enter_context(patch.object(strategy,"run",observed))
        wrap(stack,strategy.confluence_engine,"evaluate","confluence")
        wrap(stack,strategy.trade_quality_engine,"evaluate","quality")
        wrap(stack,strategy.market_regime_engine,"evaluate","regime")
        result=runtime.run()
    for trade in runtime.completed:
        trade.update(metadata[trade["entry_index"]])
        trade.pop("position_id") # Random operational identity is not research identity.
    state=runtime.account.get_state(); states=runtime.states
    days={}
    for s in states: days[s["trading_day"]]=s["daily_pnl"]
    streak=longest=0
    for t in runtime.completed:
        streak=streak+1 if t["net_pnl"]<0 else 0; longest=max(longest,streak)
    transitions=sum(s["trading_blocked"] and (i==0 or not states[i-1]["trading_blocked"]) for i,s in enumerate(states))
    submissions=session.submission_results
    return {"contract":contract,"boundary":boundary,"costs":runtime.costs.__dict__,"config_hash":runtime.config_hash,
            "legacy":legacy_metrics,"eligible":len(candles),"opportunities":len(opportunities),
            "accepted":sum(s.get("accepted") is True for s in submissions),
            "rejected":sum(s.get("accepted") is not True for s in submissions),
            "risk_vetoes":len({r["index"] for r in runtime.risk_evaluations if not r["approved"]}),
            "completed_trades":len(runtime.completed),"gross_pnl":sum(t["gross_pnl"] for t in runtime.completed),
            "net_pnl":sum(t["net_pnl"] for t in runtime.completed),"account":state,
            "peak_equity":max(s["equity"] for s in states),"minimum_equity":min(s["equity"] for s in states),
            "max_drawdown":max(s["drawdown"] for s in states),"daily_pnl":days,
            "largest_losing_day":min([0,*days.values()]),"consecutive_losses":longest,"trading_blocks":transitions,
            "terminal_unresolved_positions":len(runtime.lifecycle.get_active_positions()),
            "differences":differences,"difference_counts":dict(Counter(d["classification"] for d in differences)),
            "trades":runtime.completed,"journal_completed":len(runtime.journal.get_closed_trades()),
            "account_pnl_matches_journal":state["realized_pnl"]==sum(t.pnl for t in runtime.journal.trades),
            "result_pnl_matches_account":sum(t.pnl for t in result.trades)==state["realized_pnl"]}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract");parser.add_argument("boundary",type=float)
    args=parser.parse_args()
    boundary=int(args.boundary) if args.boundary.is_integer() else args.boundary
    OUT.mkdir(exist_ok=True)
    jobs = [(args.contract,boundary)] if args.contract!="ALL" else [
        (s["contract"],b) for s in read(EVIDENCE/"predeclared_experiment.json")["segments"] for b in (90,80,80.5)]
    with ProcessPoolExecutor(max_workers=3) as pool:
        pending={}
        for contract,b in jobs:
            path=OUT/(contract+"_"+str(b).replace(".","_")+"_C0.json")
            if path.exists():
                saved=read(path)
                assert saved["contract"]==contract and saved["boundary"]==b and saved["costs"]==HistoricalCostsV1().__dict__
                assert saved["difference_counts"].get("UNEXPLAINED",0)==0
                continue
            pending[pool.submit(replay,contract,b)]=path
        for future in as_completed(pending):
            result=future.result()
            write(pending[future],result)
            print(json.dumps({k:v for k,v in result.items() if k not in {"trades","differences","daily_pnl","account"}},default=str),flush=True)
