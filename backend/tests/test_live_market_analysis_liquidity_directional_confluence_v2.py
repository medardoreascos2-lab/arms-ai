from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)


class CapturingConfluenceEngine:
    def __init__(self):
        self.last_components = None

    def evaluate(self, **kwargs):
        self.last_components = dict(kwargs)

        return {
            "score": 0.0,
            "grade": "C",
            "components": dict(kwargs),
        }


def build_service():
    service = object.__new__(
        LiveMarketAnalysisService
    )

    service.confluence_engine_v2 = (
        CapturingConfluenceEngine()
    )

    # Force supplied smart_money_v2 fixture to be used.
    service.smart_money_engine_v2 = None

    return service


def evaluate_liquidity(
    *,
    trend,
    sweep_side=None,
    liquidity_type="NONE",
):
    service = build_service()

    structure = {
        "bos": False,
        "choch": False,
        "liquidity_sweep": (
            sweep_side is not None
        ),
        "sweep_side": sweep_side,
        "direction": "RANGE",
    }

    equal_levels = {
        "equal_highs": (
            liquidity_type in {
                "BUY_SIDE",
                "BOTH",
            }
        ),
        "equal_lows": (
            liquidity_type in {
                "SELL_SIDE",
                "BOTH",
            }
        ),
        "liquidity_type": liquidity_type,
    }

    result = {
        "trend": trend,
        "smart_money_v2": {
            "structure": structure,
            "fvg": {
                "fvg": False,
                "direction": "NEUTRAL",
            },
            "order_block": {
                "order_block": False,
                "direction": "NEUTRAL",
            },
            "equal_levels": equal_levels,
        },
        "probability": 0.90,
    }

    service._evaluate_confluence_v2(
        result=result,
        candles=[],
        risk_approved=True,
        sizing_approved=True,
        market_regime_result=None,
    )

    captured = (
        service
        .confluence_engine_v2
        .last_components
    )

    if "liquidity_score" not in captured:
        raise AssertionError(
            "Expected liquidity_score in "
            f"ConfluenceEngineV2 call, got: "
            f"{sorted(captured)}"
        )

    return captured["liquidity_score"]


def test_buy_side_sweep_is_not_full_bullish_confirmation():
    score = evaluate_liquidity(
        trend="ALCISTA",
        sweep_side="BUY_SIDE",
    )

    assert score == 0.0


def test_sell_side_sweep_is_not_full_bearish_confirmation():
    score = evaluate_liquidity(
        trend="BAJISTA",
        sweep_side="SELL_SIDE",
    )

    assert score == 0.0


def test_sell_side_sweep_supports_bullish_rejection():
    score = evaluate_liquidity(
        trend="ALCISTA",
        sweep_side="SELL_SIDE",
    )

    assert score == 1.0


def test_buy_side_sweep_supports_bearish_rejection():
    score = evaluate_liquidity(
        trend="BAJISTA",
        sweep_side="BUY_SIDE",
    )

    assert score == 1.0


def test_no_liquidity_preserves_neutral_baseline():
    score = evaluate_liquidity(
        trend="ALCISTA",
    )

    assert score == 0.50


def test_pending_equal_highs_are_not_part_of_sweep_contract():
    score = evaluate_liquidity(
        trend="ALCISTA",
        liquidity_type="BUY_SIDE",
    )

    # Equal highs are a pending BUY_SIDE liquidity pool.
    # This test intentionally records current behavior.
    # Pool semantics will be handled separately from sweep semantics.
    assert score == 1.0


def test_pending_equal_lows_are_not_part_of_sweep_contract():
    score = evaluate_liquidity(
        trend="BAJISTA",
        liquidity_type="SELL_SIDE",
    )

    # Equal lows are a pending SELL_SIDE liquidity pool.
    # This test intentionally records current behavior.
    # Pool semantics will be handled separately from sweep semantics.
    assert score == 1.0
