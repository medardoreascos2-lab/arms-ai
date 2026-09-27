"""Sprint02 HTF equivalence falsification on explicitly declared reference data.

This is a diagnostic oracle, not a supported replay/HTF adapter. It is never
installed in production. No executor, signal submission or threshold override
is used. Fresh source exports must not be treated as canonical reference data.
"""
from collections import Counter, deque
from dataclasses import asdict, replace
from datetime import timedelta
import hashlib
import json

from backend.backtesting.closed_bar_aggregator_v1 import ClosedBarAggregatorV1
from backend.models.candle import Candle
from backend.strategies.parameterized_strategy_runner_v2 import ParameterizedStrategyRunnerV2


def sequence_group_oracle(candles, *, history_limit=50):
    """Prefix-only complete groups anchored at first row or discontinuity.

    Only pending groups reset at a gap; completed history is retained, as in
    V29R. Clearing that history too would be an additional semantic change.
    Naive labels are treated as ordered tokens with nominal one-minute spacing,
    never as Chicago/UTC instants. No partial final group is emitted.
    """
    if history_limit <= 0:
        raise ValueError("positive history_limit required")
    periods = {"15m": 15, "1h": 60}
    pending = {tf: [] for tf in periods}
    completed = {tf: deque(maxlen=history_limit) for tf in periods}
    counts = dict.fromkeys(periods, 0)
    previous = None
    for candle in candles:
        label = candle.timestamp
        if label.tzinfo is not None or label.second or label.microsecond:
            raise ValueError("oracle requires naive, exact-minute source labels")
        if previous is not None:
            if label <= previous:
                raise ValueError("source labels must already be strictly ordered")
            if label - previous != timedelta(minutes=1):
                pending = {tf: [] for tf in periods}
        previous = label
        for tf, period in periods.items():
            group = pending[tf]
            group.append(candle)
            if len(group) == period:
                completed[tf].append(Candle(
                    candle.symbol, tf, group[0].open,
                    max(c.high for c in group), min(c.low for c in group),
                    group[-1].close, sum(c.volume for c in group), group[0].timestamp,
                ))
                counts[tf] += 1
                pending[tf] = []
        yield ({tf: [replace(c) for c in completed[tf]] for tf in periods}, dict(counts))


def _signature(bars):
    # The reference explicitly declares Chicago-open labels. Removing its offset
    # HERE compares bar membership/value boundaries, not source provenance.
    return [(c.timestamp.replace(tzinfo=None), c.open, c.high, c.low, c.close, c.volume) for c in bars]


def _decision(decision):
    return {"action": decision.action.value, "confidence": decision.confidence,
            "reason": decision.reason, "metadata": decision.metadata}


def compare_reference(candles, *, declared_reference_contract, retain_trace=False):
    """Compare unchanged strategy decisions, not orders, on V29R reference labels.

    Both arms use EMA10/SL30/TP60, confluence90 and existing quality85. No position
    feedback is simulated. If either emits BUY/SELL, this comparison must not be
    described as full-engine lifecycle equivalence beyond that decision.
    """
    if declared_reference_contract != "V29R_CHICAGO_OPEN_REFERENCE_ONLY":
        raise ValueError("explicit reference time contract required")
    canonical = ClosedBarAggregatorV1(history_limit=50)
    runners = [ParameterizedStrategyRunnerV2(ema=10, stop_loss=30, take_profit=60) for _ in range(2)]
    history = deque(maxlen=50)
    counters = Counter()
    actions = [Counter(), Counter()]
    score_stats = [{"count": 0, "sum": 0.0, "min": None, "max": None} for _ in range(2)]
    decision_hashes = [hashlib.sha256(), hashlib.sha256()]
    examples = []
    trace = []
    sequence_counts = {"15m": 0, "1h": 0}
    first_context_difference = None
    for index, (candle, (sequence, sequence_counts)) in enumerate(zip(candles, sequence_group_oracle(candles)), 1):
        canonical.update_completed(candle)
        history.append(dict(vars(candle)))
        left = {tf: canonical.history(tf) for tf in ("15m", "1h")}
        different_context = any(_signature(left[tf]) != _signature(sequence[tf]) for tf in left)
        if different_context and first_context_difference is None:
            first_context_difference = {"source_index_1based": index, "label": candle.timestamp.isoformat(),
                                        "canonical_counts": dict(canonical.emitted_counts), "sequence_counts": sequence_counts}
        for tf in left:
            counters[tf + "_history_difference_rows"] += _signature(left[tf]) != _signature(sequence[tf])
        if index < 5 or index == len(candles):
            continue
        counters["eligible_decisions"] += 1
        counters["HTF_context_difference_decisions"] += different_context
        decisions, trends = [], []
        for arm, htf in enumerate((left, sequence)):
            context = {"candle": dict(vars(candle)), "history": list(history),
                       "history_15m": [dict(vars(c)) for c in htf["15m"]],
                       "history_1h": [dict(vars(c)) for c in htf["1h"]],
                       "signal_index": index, "active_position_id": None, "has_active_position": False}
            # decision_time is intentionally absent: current strategy does not
            # read it. Canonical availability remains in the aggregator above.
            trends.append(asdict(runners[arm].trend_context_engine.analyze(context["history_1h"], context["history_15m"])))
            decision = _decision(runners[arm].run(context))
            decisions.append(decision)
            actions[arm][decision["action"]] += 1
            score = decision["metadata"].get("confluence_score")
            if score is not None:
                value = score * 100
                stats = score_stats[arm]
                stats["count"] += 1
                stats["sum"] += value
                stats["min"] = value if stats["min"] is None else min(stats["min"], value)
                stats["max"] = value if stats["max"] is None else max(stats["max"], value)
            decision_hashes[arm].update(json.dumps(decision, sort_keys=True, separators=(",", ":")).encode())
        a, b = decisions
        counters["full_decision_differences"] += a != b
        counters["action_differences"] += a["action"] != b["action"]
        counters["confluence_score_differences"] += a["metadata"].get("confluence_score") != b["metadata"].get("confluence_score")
        counters["trend_result_differences"] += trends[0] != trends[1]
        counters["allowed_direction_differences"] += trends[0]["allowed_direction"] != trends[1]["allowed_direction"]
        if (a != b or trends[0] != trends[1]) and len(examples) < 10:
            examples.append({"source_index_1based": index, "reference_label": candle.timestamp.isoformat(),
                             "canonical": a, "sequence": b, "canonical_trend": trends[0], "sequence_trend": trends[1]})
        if retain_trace:
            trace.append({"index": index, "canonical": a, "sequence": b, "trends": trends})
    for stats in score_stats:
        stats["mean"] = stats.pop("sum") / stats["count"] if stats["count"] else None
    result = {"reference_rows": len(candles), "counters": dict(counters),
              "canonical_HTF_counts": canonical.emitted_counts, "sequence_group_counts": sequence_counts,
              "canonical_actions": dict(actions[0]), "sequence_actions": dict(actions[1]),
              "canonical_scores": score_stats[0], "sequence_scores": score_stats[1],
              "decision_digests": [h.hexdigest() for h in decision_hashes],
              "first_context_difference": first_context_difference, "first_decision_examples": examples,
              "no_external_position_feedback": True, "thresholds_changed": False,
              "role": "REFERENCE_SEMANTIC_COMPARISON_NOT_FRESH_VALIDATION"}
    if retain_trace:
        result["trace"] = trace
    return result
