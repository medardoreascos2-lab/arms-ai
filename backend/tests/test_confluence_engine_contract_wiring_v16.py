"""V16 regression: canonical ConfluenceEngineV2 contract in the production
walk-forward strategy runner.

Before V16, ParameterizedStrategyRunnerV2.run() called
ConfluenceEngineV2.evaluate() with obsolete keyword arguments
(trend_context=..., market_structure=..., ema_alignment=..., momentum=...)
and then treated its dict result as an attribute-bearing object
(confluence.allowed/.score/.grade/.reasons). ConfluenceEngineV2.evaluate()'s
canonical contract (see backend/services/live_market_analysis_service.py,
the real live caller) is a plain dict keyed by trend_score/structure_score/
liquidity_score/fvg_score/ema_alignment_score/market_regime_score/
probability_score/volume_score/risk_approved/sizing_approved/
market_tradable, returning approved/status/decision/score/grade/
contributions/weights/blocking_reasons.

This suite drives the REAL (unmocked) ConfluenceEngineV2,
MarketStructureEngineV3 and TrendContextEngineV2 through
ParameterizedStrategyRunnerV2.run() with real candle data. It fails on the
pre-V16 wiring (TypeError: unexpected keyword argument 'trend_context') and
passes on the repaired V16 wiring.
"""

from __future__ import annotations

import inspect

from backend.intelligence.confluence_engine_v2 import ConfluenceEngineV2
from backend.strategies.parameterized_strategy_runner_v2 import (
    ParameterizedStrategyRunnerV2,
)
from backend.strategies.trading_strategy_v2 import TradingActionV2


def _flat_history(count: int = 60, start: float = 100.0):
    history = []
    price = start

    for index in range(count):
        price += 1.0
        history.append(
            {
                "open": price - 0.5,
                "high": price + 1.0,
                "low": price - 1.0,
                "close": price,
                "volume": 1000 + index,
            }
        )

    return history


def _zigzag_uptrend(
    waves: int = 6,
    wave_len: int = 10,
    rally: float = 12.0,
    pullback: float = 6.0,
    base: float = 100.0,
    final_push: float = 15.0,
):
    """A real, arbitrary swing structure (not a straight line/Fake double)."""

    candles = []
    price = base

    for _ in range(waves):
        for _ in range(wave_len // 2):
            price += rally / (wave_len // 2)
            candles.append(
                {
                    "open": price - 1,
                    "high": price + 1,
                    "low": price - 2,
                    "close": price,
                    "volume": 1000,
                }
            )

        for _ in range(wave_len // 2):
            price -= pullback / (wave_len // 2)
            candles.append(
                {
                    "open": price + 1,
                    "high": price + 2,
                    "low": price - 1,
                    "close": price,
                    "volume": 1000,
                }
            )

    price += final_push
    candles.append(
        {
            "open": price - 1,
            "high": price + 3,
            "low": price - 1,
            "close": price,
            "volume": 1000,
        }
    )

    return candles


def _context(history):
    return {
        "candle": history[-1],
        "history": history,
        "history_15m": history,
        "history_1h": history,
        "has_active_position": False,
    }


def test_confluence_engine_v2_canonical_signature_is_score_based():
    """Locks the canonical contract so a future stale caller is caught fast."""

    signature = inspect.signature(ConfluenceEngineV2.evaluate)

    assert set(signature.parameters) - {"self"} == {
        "trend_score",
        "structure_score",
        "liquidity_score",
        "fvg_score",
        "ema_alignment_score",
        "market_regime_score",
        "probability_score",
        "volume_score",
        "risk_approved",
        "sizing_approved",
        "market_tradable",
    }


def test_parameterized_strategy_runner_uses_real_confluence_engine_without_crashing():
    """The stale kwargs contract raised TypeError; the repaired one must not."""

    runner = ParameterizedStrategyRunnerV2(ema=5)

    decision = runner.run(_context(_flat_history()))

    assert decision.action in {
        TradingActionV2.HOLD,
        TradingActionV2.BUY,
        TradingActionV2.SELL,
    }

    # Real (non-canned) confluence score/grade must be present, not fabricated.
    assert "confluence_score" in decision.metadata
    assert 0.0 <= decision.metadata["confluence_score"] <= 1.0
    assert decision.metadata["grade"] in {"A+", "A", "B", "C"}


def test_confluence_engine_invoked_exactly_once_per_decision():
    """No duplicate confluence decision path per run() call."""

    runner = ParameterizedStrategyRunnerV2(ema=5)

    calls = []
    real_evaluate = runner.confluence_engine.evaluate

    def _spy(**kwargs):
        calls.append(kwargs)
        return real_evaluate(**kwargs)

    runner.confluence_engine.evaluate = _spy

    runner.run(_context(_flat_history()))

    assert len(calls) == 1

    # Canonical kwargs only; no stale trend_context/market_structure/momentum.
    assert set(calls[0]) == {
        "trend_score",
        "structure_score",
        "liquidity_score",
        "fvg_score",
        "ema_alignment_score",
        "market_regime_score",
        "probability_score",
        "volume_score",
        "risk_approved",
        "sizing_approved",
        "market_tradable",
    }

    for key in (
        "trend_score",
        "structure_score",
        "liquidity_score",
        "fvg_score",
        "ema_alignment_score",
        "market_regime_score",
        "probability_score",
        "volume_score",
    ):
        assert 0.0 <= calls[0][key] <= 1.0


def test_repeated_evaluation_is_deterministic_and_side_effect_free():
    """Evaluating the same candle history twice must not mutate/re-diverge."""

    history = _zigzag_uptrend()

    runner_a = ParameterizedStrategyRunnerV2(ema=5)
    runner_b = ParameterizedStrategyRunnerV2(ema=5)

    decision_a = runner_a.run(_context(history))
    decision_b = runner_b.run(_context(history))

    assert decision_a.action == decision_b.action
    assert decision_a.metadata.get("grade") == decision_b.metadata.get(
        "grade"
    )
    assert decision_a.metadata.get(
        "confluence_score"
    ) == decision_b.metadata.get("confluence_score")


def test_real_market_structure_score_feeds_the_canonical_structure_score():
    """structure_score must trace back to the real MarketStructureEngineV3."""

    runner = ParameterizedStrategyRunnerV2(ema=5)

    history = _zigzag_uptrend()

    captured = {}
    real_evaluate = runner.confluence_engine.evaluate

    def _spy(**kwargs):
        captured.update(kwargs)
        return real_evaluate(**kwargs)

    runner.confluence_engine.evaluate = _spy

    runner.run(_context(history))

    market_structure = runner.market_structure_engine.analyze(history)

    assert captured["structure_score"] == max(
        0.0,
        min(1.0, market_structure.score / 100.0),
    )
