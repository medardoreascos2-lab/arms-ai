from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)


class CaptureConfluenceEngine:
    def __init__(self):
        self.last_components = None

    def evaluate(self, **kwargs):
        self.last_components = dict(kwargs)

        return {
            "score": 50.0,
            "grade": "B",
            "approved": False,
            "components": {},
        }


def build_service():
    service = LiveMarketAnalysisService.__new__(
        LiveMarketAnalysisService
    )

    service.confluence_engine_v2 = CaptureConfluenceEngine()

    # Force the supplied smart_money_v2 fixture below to be used
    # directly by _evaluate_confluence_v2.
    service.smart_money_engine_v2 = None

    return service


def evaluate_pool(
    *,
    trend,
    liquidity_type="NONE",
):
    service = build_service()

    equal_highs = liquidity_type in {
        "BUY_SIDE",
        "BOTH",
    }

    equal_lows = liquidity_type in {
        "SELL_SIDE",
        "BOTH",
    }

    result = {
        "trend": trend,
        "smart_money_v2": {
            "structure": {
                "bos": False,
                "choch": False,
                "liquidity_sweep": False,
                "sweep_side": None,
                "event": "RANGE",
                "direction": "RANGE",
            },
            "fvg": {
                "fvg": False,
                "direction": "NEUTRAL",
            },
            "order_block": {
                "order_block": False,
                "direction": "NEUTRAL",
            },
            "equal_levels": {
                "equal_highs": equal_highs,
                "equal_lows": equal_lows,
                "liquidity_type": liquidity_type,
            },
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

    assert captured is not None

    assert "liquidity_score" in captured

    return captured["liquidity_score"]


def test_no_liquidity_preserves_neutral_baseline():
    assert (
        evaluate_pool(
            trend="ALCISTA",
            liquidity_type="NONE",
        )
        == 0.50
    )


def test_bullish_buy_side_pending_pool_is_not_execution_confirmation():
    assert (
        evaluate_pool(
            trend="ALCISTA",
            liquidity_type="BUY_SIDE",
        )
        == 0.50
    )


def test_bullish_sell_side_pending_pool_is_not_execution_confirmation():
    assert (
        evaluate_pool(
            trend="ALCISTA",
            liquidity_type="SELL_SIDE",
        )
        == 0.50
    )


def test_bearish_buy_side_pending_pool_is_not_execution_confirmation():
    assert (
        evaluate_pool(
            trend="BAJISTA",
            liquidity_type="BUY_SIDE",
        )
        == 0.50
    )


def test_bearish_sell_side_pending_pool_is_not_execution_confirmation():
    assert (
        evaluate_pool(
            trend="BAJISTA",
            liquidity_type="SELL_SIDE",
        )
        == 0.50
    )


def test_bullish_both_sides_pending_pools_are_not_execution_confirmation():
    assert (
        evaluate_pool(
            trend="ALCISTA",
            liquidity_type="BOTH",
        )
        == 0.50
    )


def test_bearish_both_sides_pending_pools_are_not_execution_confirmation():
    assert (
        evaluate_pool(
            trend="BAJISTA",
            liquidity_type="BOTH",
        )
        == 0.50
    )
