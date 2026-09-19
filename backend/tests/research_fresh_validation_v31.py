"""Explicit offline Sprint05 certification and predeclared independent replay.

prepare writes immutable evidence before replay can run. Native sources are read
only. Generated observation streams live under ignored data/backtest, not Git.
No production caller imports this module. No score or risk replacement occurs.
"""
import argparse
from backend.tests.private_evidence_paths_v1 import resolve_from_environment
from collections import Counter, defaultdict
from contextlib import ExitStack
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
import subprocess
from unittest.mock import patch

from backend.backtesting.historical_eligibility_v31 import HistoricalEligibilityV31, REVIEWED_CONTRACTS, MINUTE, CHICAGO
from backend.tests.research_calibration_v30 import factory, session_for, hypothetical_boundary, distribution, temporal
from backend.tests.diagnose_zero_signal_funnel_v28 import session_decisions
from backend.config.api_settings import APISettings

EVIDENCE = Path("backend/tests/research_v31/sprint05")
STREAMS = Path("data/backtest/v31_sprint05")
UTC = timezone.utc


def digest(path):
    with Path(path).open("rb") as stream:
        h = sha256()
        for block in iter(lambda: stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return resolve_from_environment(json.loads(Path(path).read_text(encoding="utf-8-sig")))


def write(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, default=str, allow_nan=False)
        stream.write("\n")


def risk_snapshot(engine):
    settings = APISettings()
    names = ("maximum_quote_age_seconds", "minimum_reward_risk_ratio", "minimum_stop_points",
             "maximum_stop_points", "maximum_spread_points", "minimum_atr_points",
             "minimum_a_plus_probability", "minimum_a_plus_confluence_score",
             "maximum_signal_age_seconds", "maximum_open_positions")
    return {"signal_risk_context": session_for(engine).signal_risk_context,
            "settings": {name: getattr(settings, name) for name in names}}


def submission_records(session):
    # Legacy session also appends independent SimulatedTrade objects here.
    # They are outcome records, not additional submission/acceptance events.
    return [s for s in session.submission_results if isinstance(s, dict)]


def next_session(policy, day):
    day += timedelta(days=1)
    while policy.session_bounds(day) is None:
        day += timedelta(days=1)
    return day


def certify_rollover(policy, old, new, old_contract, next_contract):
    """No outcomes: compare only two already completed consecutive sessions."""
    sessions = []
    day = max(min(old), min(new)).astimezone(CHICAGO).date()
    end_day = min(max(old), max(new)).astimezone(CHICAGO).date()
    streak = []
    while day <= end_day:
        bounds = policy.session_bounds(day)
        if bounds:
            start, end = (t.astimezone(UTC) for t in bounds)
            a = {t: v for t, v in old.items() if start <= t < end}
            b = {t: v for t, v in new.items() if start <= t < end}
            shared = a.keys() & b.keys()
            covered = min(old) <= start and min(new) <= start and max(old)+MINUTE >= end and max(new)+MINUTE >= end
            entry = {"trading_date": str(day), "start": start, "completed_at": end,
                     "coverage_brackets_session": covered, "old_volume": sum(a.values()),
                     "next_volume": sum(b.values()), "shared_minutes": len(shared),
                     "old_shared_volume": sum(a[t] for t in shared), "next_shared_volume": sum(b[t] for t in shared)}
            leads = covered and bool(shared) and entry["next_volume"] > entry["old_volume"] and entry["next_shared_volume"] > entry["old_shared_volume"]
            entry["next_leads_both"] = leads
            sessions.append(entry)
            streak = (streak+[entry])[-2:] if leads else []
            if len(streak) == 2:
                switch = policy.session_bounds(next_session(policy, day))[0].astimezone(UTC)
                supported = switch in old and switch in new and end-MINUTE in old
                return {"old": old_contract, "next": next_contract, "sessions": sessions,
                        "confirmation": streak, "boundary": switch, "certified": supported,
                        "boundary_first_minute_both_sources": switch in old and switch in new,
                        "old_confirmation_last_minute_present": end-MINUTE in old}
        day += timedelta(days=1)
    return {"old": old_contract, "next": next_contract, "sessions": sessions, "certified": False}


def serialized(row):
    return {"source_row": row.source_row, "raw_row": row.raw_row,
            "canonical_timestamp": row.canonical_timestamp.isoformat(), "available_at": row.available_at.isoformat(),
            "source_observation_valid": row.source_observation_valid,
            "strategy_context_eligible": row.strategy_context_eligible,
            "execution_price_eligible": row.execution_price_eligible,
            "session_accounting_eligible": row.session_accounting_eligible,
            "trading_date": row.trading_date, "anomaly_reasons": list(row.anomaly_reasons)}


def prepare():
    EVIDENCE.mkdir(exist_ok=True)
    STREAMS.mkdir(exist_ok=True)
    prior = read("backend/tests/research_v31/sprint03_provenance_evidence.json")
    provenance = read("backend/tests/research_v31/sprint04_provenance_reopen.json")
    policy = HistoricalEligibilityV31(prior["template_snapshot"])
    assert digest(prior["template_snapshot"]["path"]) == policy.digest
    for control in provenance["controls"].values():
        assert digest(control["source_path"]) == control["source_sha256"]
        assert digest(control["control_path"]) == control["control_sha256"]
    records = prior["source_records"]
    assert tuple(r["contract"] for r in records) == REVIEWED_CONTRACTS
    # Select by contract rather than relying on ordering of the earlier manifest.
    baseline_sources = [r for r in read("backend/tests/research_v31/contract_manifest.json")["selected_sources"] if r["contract"] == "SEP26"]
    baseline_hashes = {digest(r["path"]) for r in baseline_sources}
    baseline_lines = set(Path(baseline_sources[0]["path"]).read_text(encoding="utf-8-sig").splitlines())
    baseline_keys = set()
    baseline_canonical = set()
    for raw in baseline_lines:
        f = raw.split(";")
        stamp = datetime.strptime(f[0], "%Y%m%d %H%M%S")
        numeric = tuple(Decimal(x) for x in f[1:])
        baseline_keys.add((stamp, numeric))
        # Both comparable native mapping and frozen V30 naive-Chicago convention.
        baseline_canonical.add(((stamp.replace(tzinfo=UTC)-MINUTE), numeric))
        baseline_canonical.add((stamp.replace(tzinfo=CHICAGO).astimezone(UTC), numeric))
    maps, source_evidence, anomalies = {}, [], []
    leakage = Counter(source_identity=0, raw_row_identity=0, timestamp_ohlcv=0, canonical_timestamp_ohlcv=0)
    for record in records:
        contract = record["contract"]
        rows = policy.load_native(record["source_path"], contract=contract, expected_sha256=record["sha256"])
        leakage["source_identity"] += record["sha256"] in baseline_hashes
        for r in rows:
            leakage["raw_row_identity"] += r.raw_row in baseline_lines
            leakage["timestamp_ohlcv"] += (r.available_at.replace(tzinfo=None), r.ohlcv) in baseline_keys
            leakage["canonical_timestamp_ohlcv"] += (r.canonical_timestamp.astimezone(UTC), r.ohlcv) in baseline_canonical
            if r.anomaly_reasons:
                control = provenance["controls"].get(contract)
                anomalies.append({"contract": contract, "source_file": r.source_file, "source_sha256": r.source_sha256,
                                  "calendar_sha256": r.calendar_sha256, **serialized(r),
                                  "direct_control_reproduction": bool(control and r.source_row >= control["suffix_start_1based"]),
                                  "evidence": "UTC/end native mapping; reviewed ETH template and contract termination"})
        maps[contract] = {r.canonical_timestamp.astimezone(UTC): r.ohlcv[4] for r in rows if r.execution_price_eligible}
        source_evidence.append({"contract": contract, "source_file": record["source_path"], "source_sha256": record["sha256"],
                                "source_valid": len(rows), "eligible": len(maps[contract]), "ineligible": len(rows)-len(maps[contract])})
        print(json.dumps(source_evidence[-1]), flush=True)
    assert sum(leakage.values()) == 0, "V30 leakage: stop before replay"
    assert len(anomalies) == 295
    rollovers = [certify_rollover(policy, maps[a], maps[b], a, b) for a, b in zip(REVIEWED_CONTRACTS, REVIEWED_CONTRACTS[1:])]
    # Largest contiguous supported component selected solely from source/calendar.
    groups, group = [], [REVIEWED_CONTRACTS[0]]
    for pair in rollovers:
        if pair["certified"]:
            group.append(pair["next"])
        else:
            groups.append(group)
            group = [pair["next"]]
    groups.append(group)
    chosen = max(groups, key=len)
    assert len(chosen) >= 2, "no useful certified contiguous subset"
    boundaries = {(r["old"], r["next"]): r["boundary"] for r in rollovers if r["certified"]}
    segments = []
    for i, contract in enumerate(chosen):
        record = next(r for r in records if r["contract"] == contract)
        rows = policy.load_native(record["source_path"], contract=contract, expected_sha256=record["sha256"])
        lo = boundaries[chosen[i-1], contract] if i else rows[0].canonical_timestamp.astimezone(UTC)
        hi = boundaries[contract, chosen[i+1]] if i+1 < len(chosen) else rows[-1].available_at
        selected = [r for r in rows if lo <= r.canonical_timestamp.astimezone(UTC) < hi]
        path = STREAMS/(contract+".jsonl")
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            for row in selected:
                stream.write(json.dumps(serialized(row), separators=(",", ":"))+"\n")
        segments.append({"contract": contract, "source_file": record["source_path"], "source_sha256": record["sha256"],
                         "stream": str(path), "stream_sha256": digest(path), "start_inclusive": lo, "end_exclusive": hi,
                         "observations": len(selected), "eligible": sum(r.execution_price_eligible for r in selected),
                         "ineligible": sum(not r.execution_price_eligible for r in selected),
                         "terminal_reason": "CONTRACT_SEGMENT_BOUNDARY" if i+1 < len(chosen) else "CONTRACT_TERMINATION_OR_DATASET_END"})
    evidence = {"sources": source_evidence, "anomalies": anomalies, "rollovers": rollovers, "leakage": dict(leakage),
                "controls": provenance["controls"], "baseline_sources": [{"path": r["path"], "sha256": digest(r["path"])} for r in baseline_sources],
                "certification": "RESEARCH_GRADE_PROVENANCE_AND_EXECUTION_ELIGIBILITY",
                "limitations": "Current calendar snapshot is not export-time archive. 59 anomalies directly reproduced; remainder cohort-inferred. Missing open minutes are not filled."}
    write(EVIDENCE/"certification.json", evidence)
    declaration = {"frozen_at_utc": datetime.now(UTC), "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                   "phase": "BEFORE_ANY_FRESH_PERFORMANCE", "boundaries": [90, 80, 80.5], "quality": 85,
                   "parameters": {"ema": 10, "stop_loss": 30, "take_profit": 60}, "production_boundary": 90,
                   "calendar": prior["template_snapshot"], "segments": segments, "certification_sha256": digest(EVIDENCE/"certification.json"),
                   "policy_sha256": digest("backend/backtesting/historical_eligibility_v31.py"),
                   "research_helper_sha256": digest(__file__),
                   "accounting": "Independent simulator SL/TP completed outcomes only; END_OF_DATA censored valuation and lifecycle completions separate. No continuous equity.",
                   "aggregation": "RESEARCH_SUM_OF_INDEPENDENT_EXPERIMENTS",
                   "sample_screen": {"completed_minimum": 30, "segments_with_trades_minimum": 4, "max_positive_pnl_segment_share": .5},
                   "classification_rule": "Below sample screen: INSUFFICIENT_EVIDENCE. Otherwise net<=0 or PF<=1: REJECTED_BY_FRESH_DATA. Positive net/PF>1 and positive segment majority and concentration<=.5: SUPPORTED_FOR_FURTHER_RESEARCH, otherwise INSUFFICIENT_EVIDENCE. No production promotion.",
                   "unchanged": ["scores", "weights", "risk", "quality", "SL/TP", "SL-first", "submission safety", "flat semantics", "complete HTF", "strategy logic"],
                   "risk_configuration": risk_snapshot(factory()),
                   "risk_limitations": "Existing historical composition supplies daily_pnl=0 and total_drawdown=0; this is not a continuous account-risk certification. No changes or new overrides."}
    write(EVIDENCE/"predeclared_experiment.json", declaration)
    print(json.dumps({"prepared_segments": len(segments), "rollovers": sum(r["certified"] for r in rollovers), "selected_rows": sum(s["observations"] for s in segments), "leakage": dict(leakage)}), flush=True)


def load_segment(policy, segment):
    assert digest(segment["stream"]) == segment["stream_sha256"]
    assert digest(segment["source_file"]) == segment["source_sha256"]
    rows = []
    with Path(segment["stream"]).open(encoding="utf-8") as stream:
        for line in stream:
            value = json.loads(line)
            row = policy.observation(value["raw_row"], contract=segment["contract"], source_file=segment["source_file"],
                                     source_sha256=segment["source_sha256"], source_row=value["source_row"])
            assert serialized(row) == value
            rows.append(row)
    return rows


def trade_metrics(trades):
    pnls = [t["pnl"] for t in trades]
    profit, loss = sum(p for p in pnls if p > 0), -sum(p for p in pnls if p < 0)
    balance = peak = dd = 0
    for p in pnls:
        balance += p
        peak = max(peak, balance)
        dd = max(dd, peak-balance)
    return {"completed_trades": len(pnls), "wins": sum(p > 0 for p in pnls), "losses": sum(p < 0 for p in pnls),
            "breakeven": pnls.count(0), "win_rate": sum(p > 0 for p in pnls)/len(pnls) if pnls else None,
            "gross_profit": profit, "gross_loss": loss, "net_pnl": sum(pnls),
            "profit_factor": profit/loss if loss else None, "expectancy": sum(pnls)/len(pnls) if pnls else None,
            "max_drawdown": dd}


def observe(engine, candles):
    """Pass-through compact observer: originals called exactly once."""
    session, current, rows, traces = session_for(engine), {}, [], []
    strategy = session.strategy_runner_v2
    run = strategy.run
    execute = session.trade_executor_v2.execute

    def run_observed(context):
        current.clear()
        current.update(index=context["signal_index"], time=context["decision_time"].isoformat())
        local = context["candle"]["timestamp"].astimezone(CHICAGO)
        current["date"] = str(local.date()+(timedelta(days=1) if local.hour >= 17 else timedelta()))
        current["session"] = "RTH_0830_1500_CT" if (8, 30) <= (local.hour, local.minute) < (15, 0) else "ETH_OTHER"
        assert all(c["timestamp"].astimezone(UTC)+MINUTE <= context["decision_time"].astimezone(UTC) for c in context["history"])
        for key, duration in (("history_15m", 15), ("history_1h", 60)):
            assert all(c["timestamp"].astimezone(UTC)+timedelta(minutes=duration) <= context["decision_time"].astimezone(UTC) for c in context[key])
        decision = run(context)
        current["action"] = decision.action.value
        rows.append(dict(current))
        return decision

    def execute_observed(**kwargs):
        assert session.submission_results[-1].get("accepted") is True
        trade = execute(**kwargs)
        traces.append({**current, "direction": trade.direction, "pnl": trade.pnl, "reason": trade.reasoning[0],
                       "status": trade.status, "completed": trade.reasoning[0] in {"STOP_LOSS", "TAKE_PROFIT"}})
        return trade

    def wrap(stack, owner, method, key):
        original = getattr(owner, method)
        def wrapped(*args, **kwargs):
            result = original(*args, **kwargs)
            payload = asdict(result) if is_dataclass(result) else result
            current[key] = payload
            return result
        stack.enter_context(patch.object(owner, method, wrapped))

    assert session.backtest_runner_v2.replay_market_data_bridge_v2.market_data_hub_v2 is None
    assert session.signal_submission_target_v2.execution_manager.execution_mode == "PAPER"
    with ExitStack() as stack:
        stack.enter_context(patch.object(strategy, "run", run_observed))
        stack.enter_context(patch.object(session.trade_executor_v2, "execute", execute_observed))
        wrap(stack, strategy.confluence_engine, "evaluate", "confluence")
        wrap(stack, strategy.trade_quality_engine, "evaluate", "quality")
        wrap(stack, strategy.trend_context_engine, "analyze", "trend")
        wrap(stack, strategy.market_regime_engine, "evaluate", "regime")
        result = engine.run_single_pass(candles)
    return result, rows, traces


def replay_one(policy, segment, observations, boundary):
    candles = policy.eligible_candles(observations, contract=segment["contract"])
    engine = factory()
    assert risk_snapshot(engine) == segment["risk_configuration"]
    with hypothetical_boundary(engine, boundary):
        result, rows, traces = observe(engine, candles)
    plain = factory()
    assert risk_snapshot(plain) == segment["risk_configuration"]
    with hypothetical_boundary(plain, boundary):
        reference = plain.run_single_pass(candles)
    a, b = session_for(engine), session_for(plain)
    assert session_decisions(engine) == session_decisions(plain)
    assert asdict(result.statistics) == asdict(reference.statistics)
    assert result.equity_curve.__dict__ == reference.equity_curve.__dict__
    assert result.trades == reference.trades
    submissions = submission_records(a)
    assert [s.get("accepted") for s in submissions] == [s.get("accepted") for s in submission_records(b)]
    assert len(a.signal_submission_target_v2.get_trade_history()) == len(b.signal_submission_target_v2.get_trade_history())
    evaluated = [r for r in rows if "confluence" in r]
    completed = [t for t in traces if t["completed"]]
    opportunities = [{"score": r["confluence"]["score"], "index": r["index"], "time": r["time"], "date": r["date"],
                      "direction": r["trend"]["allowed_direction"]} for r in evaluated if r["confluence"]["grade"] == "A+" and r["confluence"]["approved"] and r["quality"]["approved"]]
    for t in traces:
        t["regime"] = t["regime"]["regime"]
        t["score"] = t["confluence"]["score"]
        for k in ("confluence", "quality", "trend"):
            t.pop(k, None)
    return {"contract": segment["contract"], "boundary": boundary, "candles": len(observations), "eligible": len(candles),
            "ineligible": len(observations)-len(candles), "eligible_decisions": len(rows),
            "confluence_distribution": distribution([{"score": r["confluence"]["score"]} for r in evaluated]),
            "a_plus_opportunities": len(opportunities), "clustering": temporal(opportunities),
            "actions": dict(Counter(r["action"] for r in rows)), "plans": len(a.trade_plans), "signals": len(a.signals),
            "submissions": len(submissions), "accepted": sum(s.get("accepted") is True for s in submissions),
            "rejected": sum(s.get("accepted") is not True for s in submissions),
            "rejection_reasons": dict(Counter(str(s.get("reason")) for s in submissions if s.get("accepted") is not True)),
            "simulated_trades": len(traces), **trade_metrics(completed),
            "censored_valuations": [t for t in traces if not t["completed"]], "trades": traces,
            "lifecycle_completed_trades": len(a.signal_submission_target_v2.get_trade_history()),
            "terminal_unresolved_positions": len(a.signal_submission_target_v2.get_active_positions()),
            "terminal_reason": segment["terminal_reason"], "htf_counts": dict(a.htf_aggregator.emitted_counts),
            "observer_vs_plain_full_comparison": "PASS", "lookahead_assertions": "PASS"}


def aggregate(results):
    completed = [t for r in results for t in r["trades"] if t["completed"]]
    metric = trade_metrics(completed)
    metric.pop("max_drawdown")  # Concatenation is not a portfolio equity curve.
    grouped = {}
    for field in ("direction", "regime", "session", "year"):
        groups = defaultdict(list)
        for t in completed:
            groups[t["date"][:4] if field == "year" else t[field]].append(t)
        grouped[field] = {k: {name: val for name, val in trade_metrics(v).items() if name != "max_drawdown"} for k, v in groups.items()}
    total_positive = sum(max(0, r["net_pnl"]) for r in results)
    concentration = max((max(0, r["net_pnl"]) for r in results), default=0)/total_positive if total_positive else None
    adequate = len(completed) >= 30 and sum(r["completed_trades"] > 0 for r in results) >= 4
    profitable = sum(r["net_pnl"] > 0 for r in results)
    losing = sum(r["net_pnl"] < 0 for r in results)
    classification = "INSUFFICIENT_EVIDENCE"
    if adequate and (metric["net_pnl"] <= 0 or (metric["profit_factor"] is not None and metric["profit_factor"] <= 1)):
        classification = "REJECTED_BY_FRESH_DATA"
    elif adequate and metric["profit_factor"] is not None and metric["profit_factor"] > 1 and profitable > losing and concentration <= .5:
        classification = "SUPPORTED_FOR_FURTHER_RESEARCH"
    med = lambda key: median([r[key] for r in results if r[key] is not None]) if any(r[key] is not None for r in results) else None
    return {"aggregation": "RESEARCH_SUM_OF_INDEPENDENT_EXPERIMENTS", **metric,
            "segments": len(results), "profitable_segments": profitable, "losing_segments": losing,
            "zero_completed_trade_segments": sum(r["completed_trades"] == 0 for r in results),
            "median_trades": med("completed_trades"), "median_expectancy": med("expectancy"), "median_PF": med("profit_factor"),
            "max_segment_drawdown": max(r["max_drawdown"] for r in results), "positive_pnl_concentration": concentration,
            "sample_adequate_descriptive_only": adequate, "classification": classification, "cohorts": grouped,
            "a_plus_opportunities": sum(r["a_plus_opportunities"] for r in results),
            "opportunity_episodes": sum(r["clustering"]["episodes"] for r in results),
            "simulated_trades": sum(r["simulated_trades"] for r in results),
            "censored_valuations": sum(len(r["censored_valuations"]) for r in results),
            "terminal_unresolved_positions": sum(r["terminal_unresolved_positions"] for r in results)}


def replay_job(calendar, segment, boundary):
    policy = HistoricalEligibilityV31(calendar)
    return replay_one(policy, segment, load_segment(policy, segment), boundary)


def replay():
    path = EVIDENCE/"predeclared_experiment.json"
    declaration = read(path)
    frozen_hash = digest(path)
    assert declaration["policy_sha256"] == digest("backend/backtesting/historical_eligibility_v31.py")
    helper_hash = digest(__file__)
    repair = None
    if declaration["research_helper_sha256"] != helper_hash:
        repair = read(EVIDENCE/"observer_repair.json")
        assert repair["original_helper_sha256"] == declaration["research_helper_sha256"]
        assert repair["repaired_helper_sha256"] == helper_hash
        assert repair["predeclaration_sha256"] == frozen_hash
    assert declaration["certification_sha256"] == digest(EVIDENCE/"certification.json")
    results = []
    # Independent processes only change orchestration. Each job builds fresh
    # compositions and compares observed/plain replay on the identical snapshot.
    with ProcessPoolExecutor(max_workers=3) as pool:
        pending = {}
        for segment in declaration["segments"]:
            segment = {**segment, "risk_configuration": declaration["risk_configuration"]}
            for boundary in declaration["boundaries"]:
                output = EVIDENCE/(segment["contract"]+"_"+str(boundary).replace(".", "_")+".json")
                if output.exists():
                    assert repair and repair["preserved_completed_outputs"].get(output.name) == digest(output)
                    result = read(output)
                    assert (result["contract"], result["boundary"]) == (segment["contract"], boundary)
                    results.append(result)
                else:
                    pending[pool.submit(replay_job, declaration["calendar"], segment, boundary)] = output
        for future in as_completed(pending):
            result = future.result()
            write(pending[future], result)
            results.append(result)
            print(json.dumps({k: result[k] for k in ("contract", "boundary", "eligible_decisions", "a_plus_opportunities", "accepted", "rejected", "completed_trades", "net_pnl")}), flush=True)
    order = {s["contract"]: i for i, s in enumerate(declaration["segments"])}
    results.sort(key=lambda r: (order[r["contract"]], declaration["boundaries"].index(r["boundary"])))
    aggregates = {str(b): aggregate([r for r in results if r["boundary"] == b]) for b in declaration["boundaries"]}
    sensitivity = {k: aggregates["80.5"][k]-aggregates["80"][k] for k in ("completed_trades", "net_pnl", "a_plus_opportunities")}
    assert digest(path) == frozen_hash
    write(EVIDENCE/"results.json", {"predeclaration_sha256": frozen_hash, "aggregates": aggregates, "sensitivity_80_5_minus_80": sensitivity,
                                   "runs": len(results), "production_changed": False, "executed_helper_sha256": helper_hash,
                                   "observer_repair_sha256": digest(EVIDENCE/"observer_repair.json") if repair else None})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "replay"])
    {"prepare": prepare, "replay": replay}[parser.parse_args().phase]()
