from types import SimpleNamespace

from backend.strategies.parameterized_strategy_runner_v2 import (
    ParameterizedStrategyRunnerV2,
)

from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
)


def make_history(
    count=30,
    start=100.0,
):
    return [
        {
            "open": start + index,
            "high": start + index + 2,
            "low": start + index - 2,
            "close": start + index + 1,
        }
        for index in range(count)
    ]


def make_context():

    history = make_history()

    return {
        "candle": history[-1],
        "history": history,
        "history_15m": history,
        "history_1h": history,
        "has_active_position": False,
    }


def install_common_fakes(
    runner,
    *,
    choch=False,
    quality_approved=True,
    quality_score=100,
    quality_reasons=None,
    allowed_direction="LONG",
    position_allowed=True,
    position_reason="NO ACTIVE POSITION",
):

    if quality_reasons is None:
        quality_reasons = [
            "A+ Confluence",
        ]

    runner.market_structure_engine.analyze = (
        lambda history:
        SimpleNamespace(
            trend="BULLISH",
            structure="HH_HL",
            bos=True,
            choch=choch,
        )
    )

    runner.trend_context_engine.analyze = (
        lambda candles_1h, candles_15m:
        SimpleNamespace(
            aligned=True,
            allowed_direction=allowed_direction,
        )
    )

    runner.confluence_engine.evaluate = (
        lambda **kwargs:
        SimpleNamespace(
            allowed=True,
            score=100,
            grade="A+",
            reasons=[
                "TEST A+",
            ],
        )
    )

    runner.trade_quality_engine.evaluate = (
        lambda **kwargs:
        SimpleNamespace(
            approved=quality_approved,
            score=quality_score,
            reasons=quality_reasons,
        )
    )

    runner.position_filter.evaluate = (
        lambda **kwargs:
        SimpleNamespace(
            allowed=position_allowed,
            reason=position_reason,
        )
    )

    runner.signal_controller.evaluate = (
        lambda **kwargs:
        SimpleNamespace(
            allowed=True,
            reason="FIRST SIGNAL",
        )
    )


def test_trade_quality_block_reason_is_preserved():

    runner = ParameterizedStrategyRunnerV2(
        ema=5,
    )

    install_common_fakes(
        runner,
        choch=True,
        quality_approved=False,
        quality_score=0,
        quality_reasons=[
            "Opposite CHOCH detected",
        ],
    )

    decision = runner.run(
        make_context()
    )

    assert (
        decision.action
        is TradingActionV2.HOLD
    )

    assert (
        decision.reason
        == "Opposite CHOCH detected"
    )

    assert (
        decision.metadata[
            "trade_quality_reasons"
        ]
        == [
            "Opposite CHOCH detected",
        ]
    )


def test_position_filter_blocks_existing_long():

    runner = ParameterizedStrategyRunnerV2(
        ema=5,
    )

    runner.position_state = "LONG"

    install_common_fakes(
        runner,
        position_allowed=False,
        position_reason="ALREADY LONG",
    )

    decision = runner.run(
        make_context()
    )

    assert (
        decision.action
        is TradingActionV2.HOLD
    )

    assert decision.reason == "ALREADY LONG"


def test_position_filter_blocks_reversal():

    runner = ParameterizedStrategyRunnerV2(
        ema=5,
    )

    runner.position_state = "LONG"

    install_common_fakes(
        runner,
        allowed_direction="SHORT",
        position_allowed=False,
        position_reason=(
            "CLOSE EXISTING POSITION FIRST"
        ),
    )

    decision = runner.run(
        make_context()
    )

    assert (
        decision.action
        is TradingActionV2.HOLD
    )

    assert (
        decision.reason
        == "CLOSE EXISTING POSITION FIRST"
    )


def test_clean_a_plus_can_reach_buy():

    runner = ParameterizedStrategyRunnerV2(
        ema=5,
    )

    install_common_fakes(
        runner,
        quality_approved=True,
        quality_score=100,
        allowed_direction="LONG",
        position_allowed=True,
    )

    decision = runner.run(
        make_context()
    )

    assert (
        decision.action
        is TradingActionV2.BUY
    )

    assert decision.confidence == 1.0


def test_runner_passes_a_plus_grade_to_signal_controller():

    runner = ParameterizedStrategyRunnerV2(
        ema=5,
    )

    captured = {}

    install_common_fakes(
        runner,
        quality_approved=True,
        quality_score=100,
        allowed_direction="LONG",
        position_allowed=True,
    )

    def evaluate_signal(
        **kwargs,
    ):
        captured.update(
            kwargs
        )

        return SimpleNamespace(
            allowed=True,
            reason="NEW A+ SETUP",
        )

    runner.signal_controller.evaluate = (
        evaluate_signal
    )

    decision = runner.run(
        make_context()
    )

    assert (
        decision.action
        is TradingActionV2.BUY
    )

    assert captured["grade"] == "A+"
    assert captured["direction"] == "LONG"


def test_choch_block_has_priority_over_signal_cooldown():

    runner = ParameterizedStrategyRunnerV2(
        ema=5,
    )

    install_common_fakes(
        runner,
        choch=True,
        quality_approved=False,
        quality_score=0,
        quality_reasons=[
            "Opposite CHOCH detected",
        ],
    )

    def blocked_signal(
        **kwargs,
    ):
        raise AssertionError(
            "Signal Controller must not run "
            "when Trade Quality hard-blocks."
        )

    runner.signal_controller.evaluate = (
        blocked_signal
    )

    decision = runner.run(
        make_context()
    )

    assert (
        decision.action
        is TradingActionV2.HOLD
    )

    assert (
        decision.reason
        == "Opposite CHOCH detected"
    )
