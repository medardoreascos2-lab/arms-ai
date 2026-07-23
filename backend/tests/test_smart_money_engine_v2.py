import pytest

from backend.smart_money.smart_money_engine_v2 import (
    SmartMoneyEngineV2,
)


def build_engine():
    return SmartMoneyEngineV2()


def test_detects_bullish_bos():
    engine = build_engine()

    result = engine.evaluate(
        previous_high=100.0,
        previous_low=90.0,
        current_high=102.0,
        current_low=95.0,
        close_price=101.5,
    )

    assert result["bos"] is True
    assert result["direction"] == "BULLISH"


def test_detects_bearish_bos():
    engine = build_engine()

    result = engine.evaluate(
        previous_high=100.0,
        previous_low=90.0,
        current_high=95.0,
        current_low=88.0,
        close_price=88.5,
    )

    assert result["bos"] is True
    assert result["direction"] == "BEARISH"


def test_detects_range():
    engine = build_engine()

    result = engine.evaluate(
        previous_high=100.0,
        previous_low=90.0,
        current_high=99.0,
        current_low=91.0,
        close_price=95.0,
    )

    assert result["bos"] is False
    assert result["direction"] == "RANGE"


def test_rejects_invalid_prices():
    engine = build_engine()

    with pytest.raises(ValueError):
        engine.evaluate(
            previous_high=-1,
            previous_low=90,
            current_high=100,
            current_low=95,
            close_price=96,
        )


def test_detects_bullish_choch_from_bearish_trend():
    engine = build_engine()

    result = engine.evaluate(
        previous_high=100.0,
        previous_low=90.0,
        current_high=102.0,
        current_low=95.0,
        close_price=101.5,
        previous_direction="BEARISH",
    )

    assert result["bos"] is False
    assert result["choch"] is True
    assert result["direction"] == "BULLISH"
    assert result["event"] == "CHOCH"


def test_detects_bearish_choch_from_bullish_trend():
    engine = build_engine()

    result = engine.evaluate(
        previous_high=100.0,
        previous_low=90.0,
        current_high=95.0,
        current_low=88.0,
        close_price=88.5,
        previous_direction="BULLISH",
    )

    assert result["bos"] is False
    assert result["choch"] is True
    assert result["direction"] == "BEARISH"
    assert result["event"] == "CHOCH"


def test_detects_bullish_liquidity_sweep():
    engine = build_engine()

    result = engine.evaluate(
        previous_high=100.0,
        previous_low=90.0,
        current_high=101.0,
        current_low=95.0,
        close_price=99.0,
    )

    assert result["bos"] is False
    assert result["liquidity_sweep"] is True
    assert result["sweep_side"] == "BUY_SIDE"
    assert result["event"] == "LIQUIDITY_SWEEP"


def test_detects_bearish_liquidity_sweep():
    engine = build_engine()

    result = engine.evaluate(
        previous_high=100.0,
        previous_low=90.0,
        current_high=95.0,
        current_low=89.0,
        close_price=91.0,
    )

    assert result["bos"] is False
    assert result["liquidity_sweep"] is True
    assert result["sweep_side"] == "SELL_SIDE"
    assert result["event"] == "LIQUIDITY_SWEEP"


def test_bos_has_priority_over_liquidity_sweep():
    engine = build_engine()

    result = engine.evaluate(
        previous_high=100.0,
        previous_low=90.0,
        current_high=102.0,
        current_low=95.0,
        close_price=101.5,
    )

    assert result["bos"] is True
    assert result["liquidity_sweep"] is False
    assert result["event"] == "BOS"


def test_rejects_invalid_previous_direction():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="previous_direction",
    ):
        engine.evaluate(
            previous_high=100.0,
            previous_low=90.0,
            current_high=99.0,
            current_low=91.0,
            close_price=95.0,
            previous_direction="SIDEWAYS",
        )


def test_detects_bullish_fvg():
    engine = build_engine()

    result = engine.detect_fvg(
        first_high=100.0,
        first_low=95.0,
        second_high=104.0,
        second_low=99.0,
        third_high=108.0,
        third_low=102.0,
    )

    assert result["fvg"] is True
    assert result["direction"] == "BULLISH"
    assert result["gap_low"] == 100.0
    assert result["gap_high"] == 102.0
    assert result["gap_size"] == 2.0


def test_detects_bearish_fvg():
    engine = build_engine()

    result = engine.detect_fvg(
        first_high=108.0,
        first_low=102.0,
        second_high=104.0,
        second_low=99.0,
        third_high=100.0,
        third_low=95.0,
    )

    assert result["fvg"] is True
    assert result["direction"] == "BEARISH"
    assert result["gap_low"] == 100.0
    assert result["gap_high"] == 102.0
    assert result["gap_size"] == 2.0


def test_returns_no_fvg_when_candles_overlap():
    engine = build_engine()

    result = engine.detect_fvg(
        first_high=100.0,
        first_low=95.0,
        second_high=102.0,
        second_low=97.0,
        third_high=101.0,
        third_low=96.0,
    )

    assert result["fvg"] is False
    assert result["direction"] == "NONE"
    assert result["gap_low"] is None
    assert result["gap_high"] is None
    assert result["gap_size"] == 0.0


def test_rejects_invalid_fvg_candle_ranges():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="first_high",
    ):
        engine.detect_fvg(
            first_high=90.0,
            first_low=95.0,
            second_high=104.0,
            second_low=99.0,
            third_high=108.0,
            third_low=102.0,
        )


def test_rejects_non_positive_fvg_prices():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="third_low",
    ):
        engine.detect_fvg(
            first_high=100.0,
            first_low=95.0,
            second_high=104.0,
            second_low=99.0,
            third_high=108.0,
            third_low=0.0,
        )


def test_detects_bullish_order_block():
    engine = build_engine()

    result = engine.detect_order_block(
        candle_open=100.0,
        candle_high=102.0,
        candle_low=95.0,
        candle_close=96.0,
        impulse_direction="BULLISH",
    )

    assert result["order_block"] is True
    assert result["direction"] == "BULLISH"
    assert result["zone_low"] == 95.0
    assert result["zone_high"] == 100.0
    assert result["source_candle"] == "BEARISH"


def test_detects_bearish_order_block():
    engine = build_engine()

    result = engine.detect_order_block(
        candle_open=96.0,
        candle_high=102.0,
        candle_low=95.0,
        candle_close=101.0,
        impulse_direction="BEARISH",
    )

    assert result["order_block"] is True
    assert result["direction"] == "BEARISH"
    assert result["zone_low"] == 96.0
    assert result["zone_high"] == 102.0
    assert result["source_candle"] == "BULLISH"


def test_rejects_bullish_order_block_from_bullish_candle():
    engine = build_engine()

    result = engine.detect_order_block(
        candle_open=96.0,
        candle_high=102.0,
        candle_low=95.0,
        candle_close=101.0,
        impulse_direction="BULLISH",
    )

    assert result["order_block"] is False
    assert result["direction"] == "NONE"
    assert result["zone_low"] is None
    assert result["zone_high"] is None


def test_rejects_bearish_order_block_from_bearish_candle():
    engine = build_engine()

    result = engine.detect_order_block(
        candle_open=100.0,
        candle_high=102.0,
        candle_low=95.0,
        candle_close=96.0,
        impulse_direction="BEARISH",
    )

    assert result["order_block"] is False
    assert result["direction"] == "NONE"


def test_rejects_invalid_impulse_direction():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="impulse_direction",
    ):
        engine.detect_order_block(
            candle_open=100.0,
            candle_high=102.0,
            candle_low=95.0,
            candle_close=96.0,
            impulse_direction="SIDEWAYS",
        )


def test_rejects_close_outside_order_block_candle():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="candle_close",
    ):
        engine.detect_order_block(
            candle_open=100.0,
            candle_high=102.0,
            candle_low=95.0,
            candle_close=103.0,
            impulse_direction="BULLISH",
        )


def test_detects_discount_zone():
    engine = build_engine()

    result = engine.evaluate_price_zone(
        range_high=110.0,
        range_low=90.0,
        current_price=95.0,
    )

    assert result["zone"] == "DISCOUNT"
    assert result["equilibrium"] == 100.0
    assert result["position_percent"] == 25.0


def test_detects_premium_zone():
    engine = build_engine()

    result = engine.evaluate_price_zone(
        range_high=110.0,
        range_low=90.0,
        current_price=105.0,
    )

    assert result["zone"] == "PREMIUM"
    assert result["equilibrium"] == 100.0
    assert result["position_percent"] == 75.0


def test_detects_equilibrium_zone():
    engine = build_engine()

    result = engine.evaluate_price_zone(
        range_high=110.0,
        range_low=90.0,
        current_price=100.0,
    )

    assert result["zone"] == "EQUILIBRIUM"
    assert result["equilibrium"] == 100.0
    assert result["position_percent"] == 50.0


def test_supports_boundary_prices():
    engine = build_engine()

    low_result = engine.evaluate_price_zone(
        range_high=110.0,
        range_low=90.0,
        current_price=90.0,
    )

    high_result = engine.evaluate_price_zone(
        range_high=110.0,
        range_low=90.0,
        current_price=110.0,
    )

    assert low_result["position_percent"] == 0.0
    assert low_result["zone"] == "DISCOUNT"

    assert high_result["position_percent"] == 100.0
    assert high_result["zone"] == "PREMIUM"


def test_rejects_price_outside_range():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="current_price",
    ):
        engine.evaluate_price_zone(
            range_high=110.0,
            range_low=90.0,
            current_price=115.0,
        )


def test_rejects_invalid_price_range():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="range_high",
    ):
        engine.evaluate_price_zone(
            range_high=90.0,
            range_low=110.0,
            current_price=100.0,
        )


def test_detects_equal_highs():
    engine = build_engine()

    result = engine.detect_equal_levels(
        first_high=100.0,
        second_high=100.20,
        first_low=90.0,
        second_low=92.0,
        tolerance=0.25,
    )

    assert result["equal_highs"] is True
    assert result["equal_lows"] is False
    assert result["liquidity_type"] == "BUY_SIDE"
    assert result["high_difference"] == 0.20


def test_detects_equal_lows():
    engine = build_engine()

    result = engine.detect_equal_levels(
        first_high=100.0,
        second_high=102.0,
        first_low=90.0,
        second_low=89.80,
        tolerance=0.25,
    )

    assert result["equal_highs"] is False
    assert result["equal_lows"] is True
    assert result["liquidity_type"] == "SELL_SIDE"
    assert result["low_difference"] == 0.20


def test_detects_equal_highs_and_lows():
    engine = build_engine()

    result = engine.detect_equal_levels(
        first_high=100.0,
        second_high=100.10,
        first_low=90.0,
        second_low=89.90,
        tolerance=0.25,
    )

    assert result["equal_highs"] is True
    assert result["equal_lows"] is True
    assert result["liquidity_type"] == "BOTH"


def test_returns_no_equal_levels():
    engine = build_engine()

    result = engine.detect_equal_levels(
        first_high=100.0,
        second_high=101.0,
        first_low=90.0,
        second_low=91.0,
        tolerance=0.25,
    )

    assert result["equal_highs"] is False
    assert result["equal_lows"] is False
    assert result["liquidity_type"] == "NONE"


def test_tolerance_is_inclusive():
    engine = build_engine()

    result = engine.detect_equal_levels(
        first_high=100.0,
        second_high=100.25,
        first_low=90.0,
        second_low=91.0,
        tolerance=0.25,
    )

    assert result["equal_highs"] is True


def test_rejects_negative_tolerance():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="tolerance",
    ):
        engine.detect_equal_levels(
            first_high=100.0,
            second_high=100.20,
            first_low=90.0,
            second_low=92.0,
            tolerance=-0.25,
        )


def test_rejects_non_positive_equal_level_prices():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="first_low",
    ):
        engine.detect_equal_levels(
            first_high=100.0,
            second_high=100.20,
            first_low=0.0,
            second_low=92.0,
            tolerance=0.25,
        )


def test_detects_bullish_breaker_block():
    engine = build_engine()

    result = engine.detect_breaker_block(
        original_direction="BEARISH",
        zone_low=95.0,
        zone_high=100.0,
        break_close=101.0,
        retest_price=99.0,
    )

    assert result["breaker_block"] is True
    assert result["direction"] == "BULLISH"
    assert result["zone_low"] == 95.0
    assert result["zone_high"] == 100.0
    assert result["retested"] is True


def test_detects_bearish_breaker_block():
    engine = build_engine()

    result = engine.detect_breaker_block(
        original_direction="BULLISH",
        zone_low=95.0,
        zone_high=100.0,
        break_close=94.0,
        retest_price=96.0,
    )

    assert result["breaker_block"] is True
    assert result["direction"] == "BEARISH"
    assert result["retested"] is True


def test_returns_no_breaker_without_confirmed_break():
    engine = build_engine()

    result = engine.detect_breaker_block(
        original_direction="BEARISH",
        zone_low=95.0,
        zone_high=100.0,
        break_close=99.0,
        retest_price=98.0,
    )

    assert result["breaker_block"] is False
    assert result["direction"] == "NONE"
    assert result["retested"] is False


def test_breaker_can_exist_without_retest():
    engine = build_engine()

    result = engine.detect_breaker_block(
        original_direction="BEARISH",
        zone_low=95.0,
        zone_high=100.0,
        break_close=101.0,
        retest_price=103.0,
    )

    assert result["breaker_block"] is True
    assert result["direction"] == "BULLISH"
    assert result["retested"] is False


def test_rejects_invalid_breaker_direction():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="original_direction",
    ):
        engine.detect_breaker_block(
            original_direction="SIDEWAYS",
            zone_low=95.0,
            zone_high=100.0,
            break_close=101.0,
            retest_price=99.0,
        )


def test_rejects_invalid_breaker_zone():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="zone_high",
    ):
        engine.detect_breaker_block(
            original_direction="BEARISH",
            zone_low=100.0,
            zone_high=95.0,
            break_close=101.0,
            retest_price=99.0,
        )


def test_detects_bullish_mitigation_block():
    engine = build_engine()

    result = engine.detect_mitigation_block(
        direction="BULLISH",
        zone_low=95.0,
        zone_high=100.0,
        current_low=97.0,
        current_high=103.0,
        current_close=102.0,
    )

    assert result["mitigation_block"] is True
    assert result["direction"] == "BULLISH"
    assert result["touched"] is True
    assert result["respected"] is True


def test_detects_bearish_mitigation_block():
    engine = build_engine()

    result = engine.detect_mitigation_block(
        direction="BEARISH",
        zone_low=95.0,
        zone_high=100.0,
        current_low=92.0,
        current_high=98.0,
        current_close=93.0,
    )

    assert result["mitigation_block"] is True
    assert result["direction"] == "BEARISH"
    assert result["touched"] is True
    assert result["respected"] is True


def test_returns_touched_but_not_respected():
    engine = build_engine()

    result = engine.detect_mitigation_block(
        direction="BULLISH",
        zone_low=95.0,
        zone_high=100.0,
        current_low=96.0,
        current_high=99.0,
        current_close=97.0,
    )

    assert result["mitigation_block"] is True
    assert result["touched"] is True
    assert result["respected"] is False


def test_returns_no_mitigation_without_touch():
    engine = build_engine()

    result = engine.detect_mitigation_block(
        direction="BULLISH",
        zone_low=95.0,
        zone_high=100.0,
        current_low=101.0,
        current_high=105.0,
        current_close=104.0,
    )

    assert result["mitigation_block"] is False
    assert result["touched"] is False
    assert result["respected"] is False


def test_rejects_invalid_mitigation_direction():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="direction",
    ):
        engine.detect_mitigation_block(
            direction="SIDEWAYS",
            zone_low=95.0,
            zone_high=100.0,
            current_low=97.0,
            current_high=103.0,
            current_close=102.0,
        )


def test_rejects_invalid_mitigation_candle():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="current_high",
    ):
        engine.detect_mitigation_block(
            direction="BULLISH",
            zone_low=95.0,
            zone_high=100.0,
            current_low=103.0,
            current_high=101.0,
            current_close=102.0,
        )
