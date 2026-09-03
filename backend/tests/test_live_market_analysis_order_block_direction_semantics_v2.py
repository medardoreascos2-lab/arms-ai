from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)


class CaptureConfluenceEngine:
    def __init__(self):
        self.kwargs = None

    def evaluate(self, **kwargs):
        self.kwargs = kwargs
        return {
            "score": 50.0,
            "grade": "B",
            "approved": False,
            **kwargs,
        }


def evaluate_order_block(
    *,
    trend: str,
    order_block_type: str,
) -> float:
    capture = CaptureConfluenceEngine()

    service = object.__new__(
        LiveMarketAnalysisService
    )

    service.confluence_engine_v2 = capture
    service.smart_money_engine_v2 = None

    result = {
        "trend": trend,
        "smart_money_v2": {
            "structure": {
                "bos": False,
                "choch": False,
                "direction": "RANGE",
            },
            "fair_value_gap": {
                "fvg": False,
                "type": "NONE",
            },
            "liquidity": {
                "liquidity_sweep": False,
                "sweep_side": "NONE",
                "liquidity_type": "NONE",
                "equal_highs": False,
                "equal_lows": False,
            },
            "order_block": {
                "order_block": True,
                "direction": order_block_type,
            },
        },
    }

    service._evaluate_confluence_v2(
        result=result,
        candles=[],
        risk_approved=True,
        sizing_approved=True,
        market_regime_result=None,
    )

    assert capture.kwargs is not None

    return capture.kwargs["structure_score"]


def test_bullish_order_block_aligns_with_bullish_trend():
    assert evaluate_order_block(
        trend="ALCISTA",
        order_block_type="BULLISH",
    ) == 1.0


def test_bearish_order_block_opposes_bullish_trend():
    assert evaluate_order_block(
        trend="ALCISTA",
        order_block_type="BEARISH",
    ) == 0.0


def test_bearish_order_block_aligns_with_bearish_trend():
    assert evaluate_order_block(
        trend="BAJISTA",
        order_block_type="BEARISH",
    ) == 1.0


def test_bullish_order_block_opposes_bearish_trend():
    assert evaluate_order_block(
        trend="BAJISTA",
        order_block_type="BULLISH",
    ) == 0.0
