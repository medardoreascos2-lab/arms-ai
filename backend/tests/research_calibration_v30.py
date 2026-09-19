"""Explicit offline V30 research; never imported by production.

Run baseline first, write a predeclaration from its score-only evidence, then
run replay. Output files are exclusive-create and may not replace existing work.
The hypothetical A+ boundary is instance-local; numerical scores and all risk,
quality, submission, execution and HTF authorities remain the real implementations.
"""

import argparse
from collections import Counter
from contextlib import contextmanager
import csv
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
from statistics import mean, median
import subprocess
from unittest.mock import patch

from backend.backtesting.csv_candle_loader_v2 import CsvCandleLoaderV2
from backend.backtesting.parameter_backtest_engine_factory_v2 import ParameterBacktestEngineFactoryV2
from backend.config.api_settings import APISettings
from backend.services.market_hours_service_v2 import MarketHoursServiceV2
from backend.tests.diagnose_zero_signal_funnel_v28 import collect, session_decisions

PARAMETERS = {"ema": 10, "stop_loss": 30, "take_profit": 60}
THRESHOLDS = [90, 87.5, 85, 82.5, 80, 77.5, 75, 72.5, 70, 67.5, 65, 60]
PERCENTILES = [50, 75, 80, 85, 90, 95, 97, 99, 99.5, 100]
COMPONENTS = ["trend", "structure", "liquidity", "fvg", "ema_alignment", "market_regime", "volume"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, payload):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False, default=str)
        stream.write("\n")


def factory():
    settings = APISettings()
    assert settings.minimum_a_plus_probability == 0.8
    assert settings.minimum_a_plus_confluence_score == 0.8
    return ParameterBacktestEngineFactoryV2(csv_path=None, settings=settings)(PARAMETERS)


def session_for(engine):
    return engine.pipeline.pipeline.backtest_session_v2


def trading_date(timestamp):
    value = datetime.fromisoformat(timestamp)
    if value.tzinfo is None:
        raise ValueError("Research dates require canonical aware decision times")
    return MarketHoursServiceV2.trading_day_for(value).isoformat()


def percentile(values, p):
    """Linear interpolation at (n-1)*p/100; not rounded before aggregation."""
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * p / 100
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def distribution(rows):
    scores = [r["score"] for r in rows]
    boundaries = [0, 50, 60, 65, 70, 75, 80, 85, 90, 101]
    labels = ["0-49.99", "50-59.99", "60-64.99", "65-69.99", "70-74.99", "75-79.99", "80-84.99", "85-89.99", "90+"]
    return {
        "count": len(scores), "mean": mean(scores) if scores else None,
        "min": min(scores) if scores else None,
        "percentiles": {str(p): percentile(scores, p) for p in PERCENTILES},
        "histogram": {label: sum(lo <= s < hi for s in scores)
                      for label, lo, hi in zip(labels, boundaries, boundaries[1:])},
    }


def temporal(rows):
    """Analytical episodes: same direction/date; gap <=10 elapsed minutes.

    Consecutive clusters additionally require adjacent evaluated indices and a
    one-minute timestamp gap. No state or cooldown is fed back to the strategy.
    """
    clusters = []
    episodes = []
    previous = None
    for row in rows:
        time = datetime.fromisoformat(row["time"])
        gap = None if previous is None else (time - previous["time"]).total_seconds() / 60
        same = previous is not None and (row["direction"], row["date"]) == previous["key"]
        if not same or gap != 1 or row["index"] != previous["index"] + 1:
            clusters.append(row)
        if not same or gap > 10:
            episodes.append(row)
        previous = {"time": time, "index": row["index"], "key": (row["direction"], row["date"])}
    times = [datetime.fromisoformat(r["time"]) for r in episodes]
    gaps = [(b - a).total_seconds() / 60 for a, b in zip(times, times[1:])]
    return {"raw": len(rows), "consecutive_clusters": len(clusters), "episodes": len(episodes),
            "dates": len({r["date"] for r in rows}),
            "median_episode_spacing_minutes": median(gaps) if gaps else None,
            "directions": dict(Counter(r["direction"] for r in rows)),
            "episode_directions": dict(Counter(r["direction"] for r in episodes))}


def compact(row):
    return {"index": row["index"], "time": row["decision_time"],
            "date": trading_date(row["decision_time"]),
            "direction": row["trend"]["allowed_direction"],
            "regime": row["regime"]["regime"], "score": row["confluence"]["score"],
            "quality": row["quality"]["score"], "choch": row["structure"]["choch"],
            "tradable": row["regime"]["tradable"],
            **{c: row["confluence_inputs"][c + "_score"] for c in COMPONENTS}}


def score_analysis(rows):
    sensitivity = []
    for threshold in THRESHOLDS:
        selected = [r for r in rows if r["score"] >= threshold]
        sensitivity.append({"threshold": threshold, "passing": len(selected),
                            "percent": len(selected) * 100 / len(rows),
                            "directions": dict(Counter(r["direction"] for r in selected)),
                            "regimes": dict(Counter(r["regime"] for r in selected)),
                            "dates": len({r["date"] for r in selected}),
                            "temporal": temporal(selected)})
    # Fixed production grade boundaries: this is a score-filtered count of
    # opportunities whose unchanged quality evidence meets the hypothetical
    # minimum. Controller is before the final confluence/tradability veto.
    matrix = {str(c): {str(q): sum(r["score"] >= c and r["quality"] >= q and not r["choch"]
                                  for r in rows) for q in [85, 80, 75, 70, 60]}
              for c in [90, 85, 80, 75, 70]}
    from backend.intelligence.confluence_engine_v2 import ConfluenceEngineV2
    weights = ConfluenceEngineV2.WEIGHTS
    return {"distribution": distribution(rows),
            "direction_distributions": {d: distribution([r for r in rows if r["direction"] == d])
                                        for d in sorted({r["direction"] for r in rows})},
            "regime_distributions": {g: distribution([r for r in rows if r["regime"] == g])
                                     for g in sorted({r["regime"] for r in rows})},
            "trending_combined": distribution([r for r in rows if r["regime"].startswith("TREND_")]),
            "sensitivity": sensitivity, "quality_matrix_fixed_A_plus_90": matrix,
            "quality_counts": dict(Counter(r["quality"] for r in rows)),
            "dates": sorted({r["date"] for r in rows}),
            "component_contributions": {c: {"weight": weights[c],
                "mean": mean(r[c] * weights[c] for r in rows),
                "empirical_max": max(r[c] * weights[c] for r in rows),
                "theoretical_max": weights[c] * (0.75 if c == "structure" else 1)} for c in COMPONENTS},
            "top_score_row": max(rows, key=lambda r: r["score"])}


def baseline(candles, output, provenance):
    engine = factory()
    summary, detailed, result = collect(engine, candles)
    plain = factory()
    reference = plain.run_single_pass(candles)
    assert session_decisions(engine) == session_decisions(plain)
    assert asdict(result.statistics) == asdict(reference.statistics)
    assert result.equity_curve.__dict__ == reference.equity_curve.__dict__
    assert result.trades == reference.trades
    rows = [compact(r) for r in detailed if "confluence" in r]
    with (output / "scores.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary.pop("top_20")
    report = {"provenance": provenance, "baseline": summary,
              "observer_transparency": "PASS: complete decisions, statistics, equity state, trades",
              **score_analysis(rows)}
    write_json(output / "score_analysis.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in {"baseline", "direction_distributions", "regime_distributions"}}, default=str))


def classify_hypothetically(original, threshold):
    """Reclassify only the A+ boundary, never scores or authoritative vetoes.

    Research is restricted to >=80 so the real approved A boundary and .8
    downstream admission floors are not weakened. Quality remains >=85.
    """
    if not 80 <= threshold <= 90:
        raise ValueError("Research boundary must preserve the existing score-80 admission floor")

    def evaluate(**kwargs):
        result = original(**kwargs)
        if result["score"] >= threshold:
            result = {**result, "grade": "A+"}
        return result
    return evaluate


@contextmanager
def hypothetical_boundary(engine, threshold):
    owner = session_for(engine).strategy_runner_v2.confluence_engine
    with patch.object(owner, "evaluate", classify_hypothetically(owner.evaluate, threshold)):
        yield


def metrics(trades, days):
    pnls = [t["pnl"] for t in trades]
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    balance = peak = drawdown = 0.0
    for pnl in pnls:
        balance += pnl
        peak = max(peak, balance)
        drawdown = max(drawdown, peak - balance)
    return {"trades": len(pnls), "win_rate_percent": 100 * sum(p > 0 for p in pnls) / len(pnls) if pnls else None,
            "net_pnl": sum(pnls), "profit_factor": gross_profit / gross_loss if gross_loss else None,
            "profit_factor_note": "no losing trades; undefined" if not gross_loss else None,
            "expectancy": mean(pnls) if pnls else None, "max_drawdown": drawdown,
            "trades_per_day": len(pnls) / days if days else None,
            "long_short": dict(Counter(t["direction"] for t in trades)),
            "regimes": dict(Counter(t["regime"] for t in trades))}


def replay_one(candles, threshold, dates):
    engine = factory()
    session = session_for(engine)
    assert session.signal_submission_target_v2.execution_manager.execution_mode == "PAPER"
    assert session.backtest_runner_v2.replay_market_data_bridge_v2.market_data_hub_v2 is None
    traces = []
    original_execute = session.trade_executor_v2.execute

    def execute(**kwargs):
        # Same-decision submission is the most recent result before execution.
        assert isinstance(session.submission_results[-1], dict)
        assert session.submission_results[-1].get("accepted") is True
        trade = original_execute(**kwargs)
        traces.append({"index": len(session.candle_history), "pnl": trade.pnl,
                       "direction": trade.direction, "reasoning": trade.reasoning})
        return trade

    with hypothetical_boundary(engine, threshold), patch.object(session.trade_executor_v2, "execute", execute):
        summary, rows, result = collect(engine, candles)
    # Independently replay the same hypothesis without research observers.
    # Compare every decision, not just aggregate counts or profitable outcomes.
    plain = factory()
    with hypothetical_boundary(plain, threshold):
        reference = plain.run_single_pass(candles)
    assert session_decisions(engine) == session_decisions(plain)
    assert asdict(result.statistics) == asdict(reference.statistics)
    assert result.equity_curve.__dict__ == reference.equity_curve.__dict__
    assert [t.pnl for t in result.trades] == [t.pnl for t in reference.trades]
    assert [s.get("accepted") for s in session.submission_results if isinstance(s, dict)] == [
        s.get("accepted") for s in session_for(plain).submission_results if isinstance(s, dict)]
    assert len(session.signal_submission_target_v2.get_trade_history()) == len(
        session_for(plain).signal_submission_target_v2.get_trade_history())
    row_by_index = {r["index"]: r for r in rows}
    for trade in traces:
        row = row_by_index[trade["index"]]
        trade.update(time=row["decision_time"], date=trading_date(row["decision_time"]),
                     regime=row["regime"]["regime"], score=row["confluence"]["score"])
    assert len(traces) == len(result.trades) == summary["simulated_trades"]
    assert sum(t["pnl"] for t in traces) == result.statistics.net_profit
    total_metrics = metrics(traces, len(dates))
    assert total_metrics["max_drawdown"] == result.equity_curve.max_drawdown
    split = len(candles) // 2
    first_dates = {trading_date(r["decision_time"]) for r in rows if r["index"] <= split}
    second_dates = {trading_date(r["decision_time"]) for r in rows if r["index"] > split}
    odd, even = set(dates[::2]), set(dates[1::2])
    partitions = {
        "first_half": metrics([t for t in traces if t["index"] <= split], len(first_dates)),
        "second_half": metrics([t for t in traces if t["index"] > split], len(second_dates)),
        "odd_dates": metrics([t for t in traces if t["date"] in odd], len(odd)),
        "even_dates": metrics([t for t in traces if t["date"] in even], len(even)),
    }
    accepted = [s for s in session.submission_results if isinstance(s, dict)]
    # Return only stable evidence: no random order ids or wall-clock durations.
    return {"threshold": threshold, "quality_minimum": 85,
            **{key: summary[key] for key in ["signals", "submissions", "accepted", "rejected", "simulated_trades", "completed_lifecycle_trades", "final_counts", "htf_bars"]},
            "rejection_reasons": dict(Counter(str(s.get("reason", s.get("reasons"))) for s in accepted if s.get("accepted") is not True)),
            "metrics": total_metrics, "partitions": partitions, "trades": traces,
            "adequate_sample_screen": len(traces) >= 30 and all(p["trades"] >= 10 for p in partitions.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["baseline", "replay"])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sha = digest(args.dataset)
    candles = CsvCandleLoaderV2(csv_path=args.dataset, symbol="NQ", timeframe="1m").load()
    provenance = {"dataset": str(args.dataset), "sha256": sha, "candles": len(candles),
                  "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                  "parameters": PARAMETERS, "helper_sha256": digest(Path(__file__))}
    if args.phase == "baseline":
        baseline(candles, args.output, provenance)
    else:
        declaration_path = args.output / "predeclared_grid.json"
        declaration = json.loads(declaration_path.read_text(encoding="utf-8"))
        scores = json.loads((args.output / "score_analysis.json").read_text(encoding="utf-8"))
        assert declaration["dataset_sha256"] == sha == scores["provenance"]["sha256"]
        assert declaration["head"] == provenance["head"]
        results = []
        for threshold in declaration["a_plus_boundaries"]:
            result = replay_one(candles, threshold, scores["dates"])
            write_json(args.output / ("replay_" + str(threshold).replace(".", "_") + ".json"), result)
            print(json.dumps({k: v for k, v in result.items() if k != "trades"}), flush=True)
            results.append(result)
        write_json(args.output / "replay_results.json", {"provenance": provenance,
                   "predeclaration_sha256": digest(declaration_path), "results": results})
    assert digest(args.dataset) == sha


if __name__ == "__main__":
    main()
