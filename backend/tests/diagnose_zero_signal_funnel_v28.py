"""Offline V28 observer. Calls original methods once; never substitutes evidence.

Run explicitly with ``py -m backend.tests.diagnose_zero_signal_funnel_v28``.
The optional JSON output is diagnostic evidence, not a market dataset.
"""

from collections import Counter
from contextlib import ExitStack
from dataclasses import asdict, is_dataclass
from datetime import timedelta, timezone
import hashlib
import json
from pathlib import Path
from statistics import mean
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import patch

from backend.backtesting.csv_candle_loader_v2 import CsvCandleLoaderV2
from backend.backtesting.parameter_backtest_engine_factory_v2 import ParameterBacktestEngineFactoryV2
from backend.config.api_settings import APISettings
from backend.indicators.ema_engine import EMAEngine
from backend.market_structure.market_structure_engine_v3 import MarketStructureEngineV3
from backend.smart_money.liquidity_engine_v2 import LiquidityEngineV2
from backend.trend.trend_context_engine_v2 import TrendContextEngineV2


def snapshot(value):
    return asdict(value) if is_dataclass(value) else dict(value)


def collect(engine, candles):
    session = engine.pipeline.pipeline.backtest_session_v2
    strategy = session.strategy_runner_v2
    rows = []
    current = {}
    original_run = strategy.run

    def observe_run(context):
        current.clear()
        history = context["history"]
        index = context["signal_index"]
        assert history == session.candle_history[-session.analysis_window:]
        assert history[-1] == context["candle"]
        assert all(c["timestamp"] <= context["candle"]["timestamp"] for c in history)
        assert index == len(session.candle_history)
        if rows:
            assert index == rows[-1]["index"] + 1
        before = [dict(c) for c in history]
        htf_lengths = {}
        if "decision_time" in context:
            assert len({id(context[k]) for k in ("history", "history_15m", "history_1h")}) == 3
            for key, timeframe, period in (("history_15m", "15m", 15), ("history_1h", "1h", 60)):
                htf_lengths[timeframe] = len(context[key])
                assert len(context[key]) <= session.analysis_window
                assert all(c["timeframe"] == timeframe for c in context[key])
                assert all(c["timestamp"].astimezone(timezone.utc)+timedelta(minutes=period)
                           <= context["decision_time"].astimezone(timezone.utc) for c in context[key])
        current.update(
            index=index, timestamp=str(context["candle"]["timestamp"]),
            history_length=len(history), symbol=context["candle"]["symbol"],
            timeframe=context["candle"]["timeframe"],
            htf_alias=(context["history_15m"] is history and context["history_1h"] is history),
            htf_15m_length=htf_lengths.get("15m"), htf_1h_length=htf_lengths.get("1h"),
            decision_time=str(context.get("decision_time")),
        )
        decision = original_run(context)
        assert before == history
        if "trend" in current:
            assert asdict(TrendContextEngineV2().analyze(context["history_1h"], context["history_15m"])) == current["trend"]
        if "confluence" in current:
            validate_mappings(current, history, strategy.ema)
        current["final_action"] = decision.action.value
        current["decision_reason"] = decision.reason
        current["metadata"] = dict(decision.metadata)
        rows.append(dict(current))
        return decision

    def wrap(stack, owner, method, key, *, capture_inputs=False, state=False):
        original = getattr(owner, method)

        def observed(*args, **kwargs):
            result = original(*args, **kwargs)
            current[key] = ({k: v for k, v in vars(owner).items() if not callable(v)}
                            if state else snapshot(result))
            if capture_inputs:
                current[key + "_inputs"] = dict(kwargs)
            return result

        stack.enter_context(patch.object(owner, method, observed))

    assert session.backtest_runner_v2.replay_market_data_bridge_v2.market_data_hub_v2 is None
    with ExitStack() as stack:
        stack.enter_context(patch.object(strategy, "run", observe_run))
        wrap(stack, strategy.market_structure_engine, "analyze", "structure")
        wrap(stack, strategy.trend_context_engine, "analyze", "trend")
        wrap(stack, strategy.liquidity_engine, "analyze", "liquidity", state=True)
        wrap(stack, strategy.smart_money_engine, "detect_fvg", "fvg")
        wrap(stack, strategy.market_regime_engine, "evaluate", "regime", capture_inputs=True)
        wrap(stack, strategy.confluence_engine, "evaluate", "confluence", capture_inputs=True)
        wrap(stack, strategy.trade_quality_engine, "evaluate", "quality")
        wrap(stack, strategy.signal_controller, "evaluate", "controller", capture_inputs=True)
        start = perf_counter()
        result = engine.run_single_pass(candles)
        elapsed = perf_counter() - start
    return summarize(rows, session, result, len(candles), elapsed, engine.minimum_candles), rows, result


def validate_mappings(row, history, ema_period):
    """Reconcile observed fields without feeding reconstructed values back."""
    inputs = row["confluence_inputs"]
    direction = row["trend"]["allowed_direction"]
    assert direction in {"LONG", "SHORT", "NONE"}
    assert inputs["trend_score"] == (1.0 if direction != "NONE" else 0.5)
    assert inputs["structure_score"] == row["structure"]["score"] / 100
    fvg = row["fvg"]
    fvg_direction = {"BULLISH": "LONG", "BEARISH": "SHORT"}.get(fvg["direction"])
    assert inputs["fvg_score"] == (0.5 if not fvg["fvg"] else float(fvg_direction == direction))
    liquidity = row["liquidity"]
    fresh_liquidity = LiquidityEngineV2(tolerance=liquidity["tolerance"], lookback=liquidity["lookback"])
    fresh_liquidity.analyze([SimpleNamespace(**c) for c in history[-(fresh_liquidity.lookback + 3):]])
    assert vars(fresh_liquidity) == liquidity
    assert asdict(MarketStructureEngineV3().analyze(history)) == row["structure"]
    sweep_direction = {"ALCISTA": "LONG", "BAJISTA": "SHORT"}.get(liquidity["sweep_direction"])
    assert inputs["liquidity_score"] == (0.5 if liquidity["sweep_detected"] == "NO" else float(sweep_direction == direction))
    regime = row["regime"]
    regime_score = (0.0 if not regime["tradable"] else regime["confidence"]
                    if regime["regime"] in {"TREND_UP", "TREND_DOWN"} else 0.5)
    assert inputs["market_regime_score"] == regime_score
    prices = [c["close"] for c in history]
    ema = EMAEngine(period=ema_period).calculate(prices)
    assert inputs["ema_alignment_score"] == float(
        (prices[-1] > ema and direction == "LONG") or (prices[-1] < ema and direction == "SHORT"))
    volumes = [float(c["volume"]) for c in history[-20:] if c.get("volume") is not None]
    volume_score = 0.5 if len(volumes) < 2 or mean(volumes[:-1]) <= 0 else min(1.0, max(0.0, volumes[-1] / mean(volumes[:-1]) / 2))
    assert abs(inputs["volume_score"] - volume_score) < 1e-12
    assert all(0 <= value <= 1 for key, value in inputs.items() if key.endswith("_score"))
    confluence = row["confluence"]
    assert confluence["score"] == round(sum(inputs[key + "_score"] * weight for key, weight in confluence["weights"].items()), 2)
    assert inputs["market_tradable"] == regime["tradable"]


def summarize(rows, session, result, total, elapsed, minimum_candles):
    evaluated = [r for r in rows if "confluence" in r]
    controllers = [r for r in rows if "controller" in r]
    scores = [r["confluence"]["score"] for r in evaluated]
    count = lambda key, field: dict(Counter(r[key][field] for r in rows if key in r))
    near = []
    for row in sorted(evaluated, key=lambda r: (-r["confluence"]["score"], r["index"]))[:20]:
        reasons = list(row["confluence"]["blocking_reasons"])
        if row["confluence"]["score"] < 90:
            reasons.append("confluence_below_A_plus_90")
        if row["structure"]["choch"]:
            reasons.append("Opposite CHOCH detected")
        if not row["quality"]["approved"]:
            reasons.append("trade_quality_below_85_or_CHOCH_veto")
        if row["trend"]["allowed_direction"] not in ("LONG", "SHORT"):
            reasons.append("no_direction")
        near.append({k: row[k] for k in (
            "index", "timestamp", "trend", "structure", "liquidity", "fvg",
            "regime", "regime_inputs", "confluence_inputs", "confluence", "quality",
        )})
        near[-1].update(required_confluence=90, required_quality=85, blocking_reasons=reasons)
    submissions = [s for s in session.submission_results if isinstance(s, dict)]
    return {
        "total_candles": total, "warmup_candles": min(minimum_candles - 1, total),
        "htf_bars": dict(session.htf_aggregator.emitted_counts) if getattr(session, "htf_aggregator", None) else None,
        "final_candle_excluded": 1 if total >= minimum_candles else 0,
        "decision_eligible_candles": len(rows), "processed": len(session.candle_history),
        "flat_candles": sum(c["high"] == c["low"] for c in session.candle_history),
        "trend_counts": count("trend", "allowed_direction"),
        "structure_counts": count("structure", "trend"),
        "liquidity_counts": dict(Counter(r["confluence_inputs"]["liquidity_score"] for r in evaluated)),
        "fvg_counts": count("fvg", "direction"), "regime_counts": count("regime", "regime"),
        "detector_not_evaluated": len(rows) - len(evaluated),
        "confluence_evaluated": len(scores), "confluence_min": min(scores) if scores else None,
        "confluence_max": max(scores) if scores else None,
        "confluence_mean": mean(scores) if scores else None,
        "confluence_grades": count("confluence", "grade"),
        "confluence_max_by_regime": {regime: max(r["confluence"]["score"] for r in evaluated if r["regime"]["regime"] == regime)
                                    for regime in sorted({r["regime"]["regime"] for r in evaluated})},
        "mapping_reconciliations_passed": len(evaluated),
        "a_plus_pass": sum(r["quality"]["approved"] and r["confluence"]["approved"] for r in evaluated),
        "a_plus_fail": sum(not(r["quality"]["approved"] and r["confluence"]["approved"]) for r in evaluated),
        "quality_scores": count("quality", "score"),
        "pre_controller_counts": dict(Counter(
            {"LONG": "BUY", "SHORT": "SELL"}.get(r["trend"]["allowed_direction"], "HOLD")
            if r.get("quality", {}).get("approved") and r.get("confluence", {}).get("approved") else "HOLD"
            for r in rows)),
        "controller_evaluated": len(controllers),
        "cooldown_blocked": sum(not r["controller"]["allowed"] and "COOLDOWN" in r["controller"]["reason"] for r in controllers),
        "other_controller_blocked": sum(not r["controller"]["allowed"] and "COOLDOWN" not in r["controller"]["reason"] for r in controllers),
        "final_counts": dict(Counter(r["final_action"] for r in rows)),
        "decision_reasons": dict(Counter(r["decision_reason"] for r in rows)),
        "trade_plans": len(session.trade_plans), "signals": len(session.signals),
        "submissions": len(submissions), "accepted": sum(s.get("accepted") is True for s in submissions),
        "rejected": sum(s.get("accepted") is not True for s in submissions),
        "simulated_trades": len(session.simulated_trades),
        "completed_lifecycle_trades": len(session.signal_submission_target_v2.get_trade_history()),
        "final_equity": result.equity_curve.balance,
        "net_profit": result.statistics.net_profit,
        "max_drawdown": result.equity_curve.max_drawdown,
        "htf_alias_count": sum(r["htf_alias"] for r in rows),
        "symbols": sorted({r["symbol"] for r in rows}), "timeframes": sorted({r["timeframe"] for r in rows}),
        "elapsed_instrumented_seconds": elapsed, "top_20": near,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and (args.output.resolve() == args.dataset.resolve() or args.output.exists()):
        raise ValueError("Diagnostic output must be a new file, separate from the dataset")
    digest = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    candles = CsvCandleLoaderV2(csv_path=args.dataset, symbol="NQ", timeframe="1m").load()
    settings = APISettings()
    parameters = {"ema": 10, "stop_loss": 30, "take_profit": 60}
    engine = ParameterBacktestEngineFactoryV2(csv_path=None, settings=settings)(parameters)
    report, rows, result = collect(engine, candles)
    # A fresh uninstrumented production run proves the observer is transparent.
    reference = ParameterBacktestEngineFactoryV2(csv_path=None, settings=settings)(parameters)
    start = perf_counter()
    reference_result = reference.run_single_pass(candles)
    report["uninstrumented_seconds"] = perf_counter() - start
    reference_session = reference.pipeline.pipeline.backtest_session_v2
    assert session_decisions(engine) == session_decisions(reference)
    assert asdict(result.statistics) == asdict(reference_result.statistics)
    assert result.equity_curve.balance == reference_result.equity_curve.balance
    assert len(result.trades) == len(reference_result.trades)
    assert len(reference_session.candle_history) == len(candles)
    report["observer_transparency"] = "PASS: all decisions, statistics, equity, trade count"
    report.update(dataset=str(args.dataset), sha256=digest, parameters=parameters,
                  minimum_probability=settings.minimum_a_plus_probability,
                  minimum_confluence=settings.minimum_a_plus_confluence_score)
    assert hashlib.sha256(args.dataset.read_bytes()).hexdigest() == digest
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "top_20"}, default=str))
    return report


def session_decisions(engine):
    return engine.pipeline.pipeline.backtest_session_v2.decisions


if __name__ == "__main__":
    main()
