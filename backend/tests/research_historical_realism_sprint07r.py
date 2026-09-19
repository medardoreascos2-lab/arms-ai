"""Predeclared cost sensitivity and descriptive cohorts; no optimization."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path

from backend.backtesting.historical_accounting_v1 import HistoricalCostsV1
from backend.accounts.account_config_manager_v2 import AccountConfigManagerV2
from backend.tests.research_fresh_validation_v31 import EVIDENCE, read, write, digest, trade_metrics
from backend.tests.research_historical_accounting_sprint07r import OUT, replay


def canonical_runs():
    declaration=read(EVIDENCE/"predeclared_experiment.json")
    paths=[OUT/(s["contract"]+"_"+str(b).replace(".","_")+"_C0.json")
           for s in declaration["segments"] for b in (90,80,80.5)]
    runs=[read(p) for p in paths]
    assert len(runs)==39
    assert all(r["difference_counts"].get("UNEXPLAINED",0)==0 and r["account_pnl_matches_journal"]
               and r["result_pnl_matches_account"] and r["journal_completed"]==r["completed_trades"] for r in runs)
    return paths,runs


def prepare():
    paths,runs=canonical_runs()
    profile=AccountConfigManagerV2().get_active_account()
    assert all(r["account"]["starting_balance"]==float(profile.account_size) for r in runs)
    scenarios=[]
    for fee in (2.5,5.0):
        for kind,ticks in (("C1",0),("C2",1),("C3",2)):
            scenarios.append({"name":kind+"_fee"+str(fee).replace(".","_"),
                              "fee_per_contract_side":fee,"slippage_ticks_side":ticks,
                              "roundtrip_fee_per_contract":fee*2,
                              "roundtrip_slippage_dollars_per_contract":ticks*.25*20*2})
    value={"declared_at_utc":datetime.now(timezone.utc).isoformat(),"phase":"BEFORE_COST_REPLAYS",
           "boundaries":[80,80.5],"production_control":90,"production_changed":False,
           "scenarios":scenarios,"tick_size":.25,"point_value":20,
           "fee_evidence":"Illustrative research assumptions, NOT an established broker/exchange fee schedule. Two fee levels and three slippage levels; no privileged winning scenario.",
           "C0":"Canonical zero-cost independent-segment baseline",
           "canonical_baseline_hashes":{str(p):digest(p) for p in paths},
           "execution_sha256":digest("backend/backtesting/historical_accounting_v1.py"),
           "research_code_sha256":{p:digest(p) for p in (
               "backend/tests/research_historical_accounting_sprint07r.py",
               "backend/tests/research_historical_realism_sprint07r.py")},
           "account_profile":{"starting_balance":profile.account_size,"daily_loss_limit":profile.daily_loss_limit,
                              "maximum_total_drawdown":profile.max_drawdown,"risk_percent":profile.risk_percent},
           "cohorts":{"early_late":"2022-2023 versus 2024-2025 by entry year",
                      "rolling":"Four consecutive independent contract segments, stride one; overlapping descriptive windows",
                      "volatility":"Mean high-low range of available analysis history: <5, 5..<15, >=15 NQ points",
                      "direction":"LONG and SHORT both retained; no strategy changes"},
           "support_rule":{"minimum_completed":30,"minimum_active_segments":4,
               "positive_expectancy":"Required in C0 and EVERY declared cost scenario",
               "concentration":"Largest positive contract contribution <=50% of sum of positive contract contributions in EVERY scenario",
               "risk":"No account hard-limit breach in ANY scenario; risk vetoes remain enforced",
               "status":"Descriptive PAPER research only; never production-ready"},
           "accounting":"No cross-contract equity splice. Side/cohort realized drawdowns are descriptive subsets per independent contract, distinct from actual account equity drawdown."}
    write(OUT/"cost_predeclaration.json",value)


def costs():
    declaration=read(OUT/"cost_predeclaration.json")
    assert digest("backend/backtesting/historical_accounting_v1.py")==declaration["execution_sha256"]
    assert all(digest(p)==h for p,h in declaration["research_code_sha256"].items())
    assert all(digest(p)==h for p,h in declaration["canonical_baseline_hashes"].items())
    contracts=[s["contract"] for s in read(EVIDENCE/"predeclared_experiment.json")["segments"]]
    with ProcessPoolExecutor(max_workers=6) as pool:
        pending={}
        for contract in contracts:
            for boundary in declaration["boundaries"]:
                for scenario in declaration["scenarios"]:
                    path=OUT/(contract+"_"+str(boundary).replace(".","_")+"_"+scenario["name"]+".json")
                    if path.exists():
                        old=read(path)
                        assert old["contract"]==contract and old["boundary"]==boundary
                        assert old["costs"]=={k:scenario[k] for k in ("fee_per_contract_side","slippage_ticks_side")}
                        continue
                    model=HistoricalCostsV1(scenario["fee_per_contract_side"],scenario["slippage_ticks_side"])
                    pending[pool.submit(replay,contract,boundary,model,False)]=(path,scenario["name"])
        for future in as_completed(pending):
            result=future.result();path,name=pending[future]
            assert result["account_pnl_matches_journal"] and result["result_pnl_matches_account"]
            write(path,result)
            print(json.dumps({"scenario":name,**{k:result[k] for k in ("contract","boundary","completed_trades","gross_pnl","net_pnl","risk_vetoes","max_drawdown")}}),flush=True)


def metrics(trades):
    value=trade_metrics([{"pnl":t["net_pnl"]} for t in trades])
    value.pop("max_drawdown")
    value["gross_pnl"]=sum(t["gross_pnl"] for t in trades)
    value["fees"]=sum(t["fees"] for t in trades)
    grouped=defaultdict(list)
    for t in trades: grouped[t["contract"]].append({"pnl":t["net_pnl"]})
    segment_metrics=[trade_metrics(ts) for ts in grouped.values()]
    value["max_independent_segment_realized_drawdown"]=max((m["max_drawdown"] for m in segment_metrics),default=0)
    positive=sum(max(0,m["net_pnl"]) for m in segment_metrics)
    drawdowns=sum(m["max_drawdown"] for m in segment_metrics)
    value["active_segments"]=len(grouped)
    value["max_contract_trade_share"]=max((len(ts) for ts in grouped.values()),default=0)/len(trades) if trades else None
    value["max_positive_contract_pnl_share"]=max((max(0,m["net_pnl"]) for m in segment_metrics),default=0)/positive if positive else None
    value["max_share_of_sum_independent_segment_realized_drawdowns"]=value["max_independent_segment_realized_drawdown"]/drawdowns if drawdowns else None
    return value


def summarize(runs, *, maximum_total_drawdown):
    trades=[t for r in runs for t in r["trades"]]
    value=metrics(trades)
    positive=sum(max(0,r["net_pnl"]) for r in runs)
    drawdown_sum=sum(r["max_drawdown"] for r in runs)
    value.update(segments=len(runs),active_segments=sum(r["completed_trades"]>0 for r in runs),
                 profitable_segments=sum(r["net_pnl"]>0 for r in runs),
                 risk_vetoes=sum(r["risk_vetoes"] for r in runs),
                 max_positive_contract_pnl_share=max((max(0,r["net_pnl"]) for r in runs),default=0)/positive if positive else None,
                 max_contract_trade_share=max((r["completed_trades"] for r in runs),default=0)/len(trades) if trades else None,
                 max_account_equity_drawdown=max(r["max_drawdown"] for r in runs),
                 max_share_of_sum_independent_segment_max_drawdowns=max(r["max_drawdown"] for r in runs)/drawdown_sum if drawdown_sum else None,
                 hard_limit_breach_segments=sum(r["max_drawdown"]>=maximum_total_drawdown for r in runs),
                 terminal_unresolved_positions=sum(r["terminal_unresolved_positions"] for r in runs),
                 trading_blocks=sum(r["trading_blocks"] for r in runs))
    cohorts={}
    for dimension in ("direction","contract","year","regime","session","volatility","early_late"):
        groups=defaultdict(list)
        for t in trades:
            if dimension=="volatility":
                key="LT5" if t["volatility_points"]<5 else "5_TO_LT15" if t["volatility_points"]<15 else "GE15"
            elif dimension=="early_late":key="2022_2023" if t["year"]<=2023 else "2024_2025"
            else:key=str(t[dimension])
            groups[key].append(t)
        cohorts[dimension]={key:metrics(ts) for key,ts in groups.items()}
        if dimension=="direction":
            for direction in ("LONG","SHORT"):
                cohorts[dimension].setdefault(direction,metrics([]))
        if dimension!="direction":
            cohorts[dimension+"_by_direction"]={key:{d:metrics([t for t in ts if t["direction"]==d]) for d in ("LONG","SHORT")} for key,ts in groups.items()}
    value["cohorts"]=cohorts
    value["rolling_four_contracts"]=[{"contracts":[r["contract"] for r in runs[i:i+4]],
        **metrics([t for r in runs[i:i+4] for t in r["trades"]])} for i in range(max(0,len(runs)-3))]
    value["segment_risk"]=[{k:r[k] for k in ("contract","accepted","rejected","risk_vetoes","completed_trades","gross_pnl","net_pnl","peak_equity","minimum_equity","max_drawdown","largest_losing_day","consecutive_losses","trading_blocks","terminal_unresolved_positions")} for r in runs]
    return value


def report():
    paths,zero=canonical_runs()
    declaration=read(OUT/"cost_predeclaration.json")
    assert digest("backend/backtesting/historical_accounting_v1.py")==declaration["execution_sha256"]
    assert all(digest(p)==h for p,h in declaration["research_code_sha256"].items())
    assert all(digest(p)==h for p,h in declaration["canonical_baseline_hashes"].items())
    contracts=[s["contract"] for s in read(EVIDENCE/"predeclared_experiment.json")["segments"]]
    summaries={}; classifications={"90":"INSUFFICIENT_EVIDENCE"}; normalization=[]
    limit=declaration["account_profile"]["maximum_total_drawdown"]
    for boundary in (90,80,80.5):
        zero_runs=[r for r in zero if r["boundary"]==boundary]
        groups={"C0":summarize(zero_runs,maximum_total_drawdown=limit)}
        scenario_runs={"C0":zero_runs}
        if boundary!=90:
            for scenario in declaration["scenarios"]:
                runs=[read(OUT/(c+"_"+str(boundary).replace(".","_")+"_"+scenario["name"]+".json")) for c in contracts]
                groups[scenario["name"]]=summarize(runs,maximum_total_drawdown=limit)
                scenario_runs[scenario["name"]]=runs
            enough=all(g["completed_trades"]>=30 and g["active_segments"]>=4 for g in groups.values())
            survives=all(g["expectancy"] is not None and g["expectancy"]>0 for g in groups.values())
            robust=all(g["max_positive_contract_pnl_share"] is not None and g["max_positive_contract_pnl_share"]<=.5
                       and g["hard_limit_breach_segments"]==0 and g["terminal_unresolved_positions"]==0 for g in groups.values())
            classifications[str(boundary)]=("REJECTED_BY_REALISM" if enough and not survives else
                "SUPPORTED_FOR_PAPER_TRADING_RESEARCH" if enough and survives and robust else "INSUFFICIENT_EVIDENCE")
        summaries[str(boundary)]=groups
        for scenario,runs in scenario_runs.items():
            for run in runs:
                for trade in run["trades"]:
                    sign=1 if trade["direction"]=="LONG" else -1
                    scale=trade["quantity"]*trade["point_value"]
                    gross=(trade["executed_exit"]-trade["executed_entry"])*sign*scale
                    assert gross==trade["gross_pnl"] and gross-trade["fees"]==trade["net_pnl"]
                    slippage=(abs(trade["executed_entry"]-trade["planned_entry"])+abs(trade["executed_exit"]-trade["trigger_price"]))*scale
                    normalization.append({"boundary":boundary,"scenario":scenario,**trade,
                        "planned_stop_distance_points":abs(trade["planned_entry"]-trade["stop"]),
                        "planned_target_distance_points":abs(trade["target"]-trade["planned_entry"]),
                        "executed_entry_to_stop_points":abs(trade["executed_entry"]-trade["stop"]),
                        "gross_stop_risk_dollars":abs(trade["executed_entry"]-trade["stop"])*scale,
                        "slippage_dollars_already_in_fills":slippage,
                        "total_execution_cost_dollars":slippage+trade["fees"],
                        "pnl_before_execution_costs":gross+slippage})
    write(OUT/"trade_accounting.json",normalization)
    write(OUT/"realism_results.json",{"classification":classifications,"scenarios":summaries,
        "predeclaration_sha256":digest(OUT/"cost_predeclaration.json"),
        "limitations":["Research-grade source provenance; see frozen V31 limitations",
                       "Planned-level gap fills preserve existing historical convention; not a live-fill guarantee",
                       "Independent contracts; no continuous cross-contract equity or universal prop-firm rule",
                       "Legacy counterfactual difference certification covers C0; cost runs replay the certified canonical path with declared costs",
                       "Costs are sensitivity assumptions; both directions retained; no threshold optimization"]})
    print(json.dumps({"classification":classifications,"net_by_scenario":{b:{k:v["net_pnl"] for k,v in groups.items()} for b,groups in summaries.items()}}))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("prepare","costs","report"))
    globals()[parser.parse_args().phase]()
