"""V17 wiring/regression: real liquidity, FVG, and market-regime detectors
in the offline walk-forward strategy runner.

Canonical owners wired here (unchanged, real, production classes):

- LIQUIDITY_CANONICAL_OWNER: backend/smart_money/liquidity_engine_v2.py
  ::LiquidityEngineV2.analyze()
- FVG_CANONICAL_OWNER: backend/smart_money/smart_money_engine_v2.py
  ::SmartMoneyEngineV2.detect_fvg()
- MARKET_REGIME_CANONICAL_OWNER: backend/market_analysis/market_regime_engine.py
  ::MarketRegimeEngine.evaluate()

Before V17, ParameterizedStrategyRunnerV2 fed ConfluenceEngineV2 an honest
neutral 0.5 for liquidity_score/fvg_score/market_regime_score because no
detector was wired in. V17 replaces those neutral constants with real
detector output, translated with the same semantics
backend/services/live_market_analysis_service.py already uses for the live
path, while never reading beyond the historical prefix supplied by the
caller (no lookahead).
"""

from __future__ import annotations

from backend.strategies.parameterized_strategy_runner_v2 import (
    ParameterizedStrategyRunnerV2,
    _estimate_fvg_score,
    _estimate_liquidity_score,
    _estimate_market_regime,
)


def _zigzag_uptrend(
    waves: int = 8,
    wave_len: int = 10,
    rally: float = 0.6,
    pullback: float = 0.10,
    base: float = 100.0,
    wick: float = 0.015,
):
    """Deterministic synthetic swing candles; detector scores are not injected."""

    candles = []
    price = base

    for _ in range(waves):
        for _ in range(wave_len // 2):
            price += rally / (wave_len // 2)
            candles.append(
                {
                    "open": price - wick,
                    "high": price + wick,
                    "low": price - 2 * wick,
                    "close": price,
                    "volume": 1000,
                }
            )

        for _ in range(wave_len // 2):
            price -= pullback / (wave_len // 2)
            candles.append(
                {
                    "open": price + wick,
                    "high": price + 2 * wick,
                    "low": price - wick,
                    "close": price,
                    "volume": 1000,
                }
            )

    price += 0.8
    candles.append(
        {
            "open": price - wick,
            "high": price + 3 * wick,
            "low": price - wick,
            "close": price,
            "volume": 5000,
        }
    )

    return candles


def _choppy_range(count: int = 80, base: float = 100.0, wobble: float = 0.5):
    """Deterministic synthetic ranging candles with contrasting structure."""

    candles = []
    price = base

    for index in range(count):
        direction = 1.0 if index % 2 == 0 else -1.0
        price += direction * wobble
        candles.append(
            {
                "open": price - 0.05,
                "high": price + 0.1,
                "low": price - 0.15,
                "close": price,
                "volume": 800,
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


def test_real_liquidity_authority_is_invoked():
    """LiquidityEngineV2.analyze is the real, unmocked authority invoked."""

    runner = ParameterizedStrategyRunnerV2(ema=5)
    history = _zigzag_uptrend()

    calls = []
    real_analyze = runner.liquidity_engine.analyze

    def _spy(candles):
        calls.append(list(candles))
        return real_analyze(candles)

    runner.liquidity_engine.analyze = _spy

    runner.run(_context(history))

    assert len(calls) == 1

    # Only real historical candles (from this exact history) were passed.
    passed_highs = {candle.high for candle in calls[0]}
    real_highs = {item["high"] for item in history}
    assert passed_highs <= real_highs


def test_real_fvg_authority_is_invoked():
    """SmartMoneyEngineV2.detect_fvg is the real, unmocked authority invoked."""

    runner = ParameterizedStrategyRunnerV2(ema=5)
    history = _zigzag_uptrend()

    calls = []
    real_detect_fvg = runner.smart_money_engine.detect_fvg

    def _spy(**kwargs):
        calls.append(kwargs)
        return real_detect_fvg(**kwargs)

    runner.smart_money_engine.detect_fvg = _spy

    runner.run(_context(history))

    assert len(calls) == 1

    first, second, third = history[-3], history[-2], history[-1]
    assert calls[0]["first_high"] == first["high"]
    assert calls[0]["second_high"] == second["high"]
    assert calls[0]["third_high"] == third["high"]


def test_real_market_regime_authority_is_invoked():
    """MarketRegimeEngine.evaluate is the real, unmocked authority invoked."""

    runner = ParameterizedStrategyRunnerV2(ema=5)
    history = _zigzag_uptrend()

    calls = []
    real_evaluate = runner.market_regime_engine.evaluate

    def _spy(**kwargs):
        calls.append(kwargs)
        return real_evaluate(**kwargs)

    runner.market_regime_engine.evaluate = _spy

    runner.run(_context(history))

    assert len(calls) == 1

    for key in (
        "directional_strength",
        "volatility_score",
        "compression_score",
    ):
        assert key in calls[0]


def test_confluence_scores_trace_back_to_real_detector_output():
    """liquidity/fvg/market_regime scores reaching ConfluenceEngineV2 are real."""

    runner = ParameterizedStrategyRunnerV2(ema=5)
    history = _zigzag_uptrend()

    captured = {}
    real_evaluate = runner.confluence_engine.evaluate

    def _spy(**kwargs):
        captured.update(kwargs)
        return real_evaluate(**kwargs)

    runner.confluence_engine.evaluate = _spy

    runner.run(_context(history))

    trend_context = runner.trend_context_engine.analyze(history, history)

    expected_liquidity = _estimate_liquidity_score(
        runner.liquidity_engine,
        history,
        trend_context.allowed_direction,
    )

    expected_fvg = _estimate_fvg_score(
        runner.smart_money_engine,
        history,
        trend_context.allowed_direction,
    )

    _, expected_regime_score, _ = _estimate_market_regime(
        runner.market_regime_engine,
        history,
    )

    assert captured["liquidity_score"] == expected_liquidity
    assert captured["fvg_score"] == expected_fvg
    assert captured["market_regime_score"] == expected_regime_score

    # Not the pre-V17 hardcoded neutral constants for every dimension at once.
    assert not (
        captured["liquidity_score"] == 0.5
        and captured["fvg_score"] == 0.5
        and captured["market_regime_score"] == 0.5
    )


def test_detectors_never_receive_more_than_the_supplied_prefix():
    """No lookahead: detectors only ever see candles inside the given prefix."""

    full_history = _zigzag_uptrend(waves=10) + _choppy_range(count=20)
    prefix = full_history[:90]

    runner = ParameterizedStrategyRunnerV2(ema=5)

    seen_highs = set()

    real_analyze = runner.liquidity_engine.analyze

    def _spy(candles):
        seen_highs.update(candle.high for candle in candles)
        return real_analyze(candles)

    runner.liquidity_engine.analyze = _spy

    runner.run(_context(prefix))

    prefix_highs = {item["high"] for item in prefix}
    future_highs = {item["high"] for item in full_history[90:]}

    assert seen_highs <= prefix_highs
    assert not (seen_highs & future_highs)


def test_same_historical_prefix_produces_same_detector_scores():
    """Reproducibility: identical prefixes yield identical detector output."""

    history = _zigzag_uptrend()

    runner_a = ParameterizedStrategyRunnerV2(ema=5)
    runner_b = ParameterizedStrategyRunnerV2(ema=5)

    trend_context = runner_a.trend_context_engine.analyze(history, history)

    liquidity_a = _estimate_liquidity_score(
        runner_a.liquidity_engine, history, trend_context.allowed_direction
    )
    liquidity_b = _estimate_liquidity_score(
        runner_b.liquidity_engine, history, trend_context.allowed_direction
    )

    fvg_a = _estimate_fvg_score(
        runner_a.smart_money_engine, history, trend_context.allowed_direction
    )
    fvg_b = _estimate_fvg_score(
        runner_b.smart_money_engine, history, trend_context.allowed_direction
    )

    assert liquidity_a == liquidity_b
    assert fvg_a == fvg_b


def test_materially_different_structures_produce_different_detector_scores():
    """A trending dataset and a choppy dataset must not collapse to identical evidence."""

    trending = _zigzag_uptrend()
    choppy = _choppy_range()

    runner_trend = ParameterizedStrategyRunnerV2(ema=5)
    runner_choppy = ParameterizedStrategyRunnerV2(ema=5)

    trend_tc = runner_trend.trend_context_engine.analyze(trending, trending)
    choppy_tc = runner_choppy.trend_context_engine.analyze(choppy, choppy)

    _, trend_regime_score, trend_tradable = _estimate_market_regime(
        runner_trend.market_regime_engine, trending
    )
    _, choppy_regime_score, choppy_tradable = _estimate_market_regime(
        runner_choppy.market_regime_engine, choppy
    )

    assert (
        trend_regime_score != choppy_regime_score
        or trend_tradable != choppy_tradable
    )


def test_no_duplicate_confluence_evaluation_with_real_detectors():
    """Wiring real detectors must not introduce a second confluence authority."""

    runner = ParameterizedStrategyRunnerV2(ema=5)
    history = _zigzag_uptrend()

    calls = []
    real_evaluate = runner.confluence_engine.evaluate

    def _spy(**kwargs):
        calls.append(kwargs)
        return real_evaluate(**kwargs)

    runner.confluence_engine.evaluate = _spy

    runner.run(_context(history))

    assert len(calls) == 1


def test_detector_evaluation_causes_no_execution_or_financial_mutation():
    """Running the strategy must not create any execution/financial side effect."""

    runner = ParameterizedStrategyRunnerV2(ema=5)
    history = _zigzag_uptrend()

    position_before = runner.position_state

    decision = runner.run(_context(history))

    assert decision is not None
    # A HOLD/no-position outcome must leave position_state untouched.
    if decision.action.name == "HOLD":
        assert runner.position_state == position_before
