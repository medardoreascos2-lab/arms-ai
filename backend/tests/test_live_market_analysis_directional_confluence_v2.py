from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)


class CaptureConfluenceEngine:
    def __init__(self):
        self.kwargs = None

    def evaluate(self, **kwargs):
        self.kwargs = dict(kwargs)

        return {
            "approved": False,
            "status": "REJECTED",
            "decision": "REJECT",
            "score": 0.0,
            "grade": "C",
            "contributions": {},
            "weights": {},
            "blocking_reasons": [],
        }


def _build_service():
    service = LiveMarketAnalysisService.__new__(
        LiveMarketAnalysisService
    )

    capture = CaptureConfluenceEngine()

    service.confluence_engine_v2 = capture
    service.smart_money_engine_v2 = None

    return service, capture


def _base_result():
    return {
        "trend": "ALCISTA",
        "probability": 0.92,
        "risk": {
            "approved": True,
        },
        "position_sizing": {
            "approved": True,
        },
        "market_context_v2": {
            "tradable": True,
        },
        "market_regime": {
            "score": 1.0,
        },
        "volume": {
            "confirmed": True,
        },
    }


def test_bearish_bos_is_not_full_positive_structure_confirmation():
    service, capture = _build_service()

    result = _base_result()

    result["smart_money_v2"] = {
        "structure": {
            "bos": True,
            "choch": False,
            "liquidity_sweep": False,
            "event": "BOS",
            "direction": "BEARISH",
        },
        "fvg": {
            "fvg": False,
            "direction": "NONE",
        },
        "order_block": {
            "order_block": False,
            "direction": "NONE",
        },
        "equal_levels": {
            "equal_highs": False,
            "equal_lows": False,
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

    assert capture.kwargs["structure_score"] == 0.0, (
        "A BEARISH BOS must contribute zero directional "
        "structure confirmation to an ALCISTA setup."
    )


def test_bearish_fvg_is_not_full_positive_fvg_confirmation():
    service, capture = _build_service()

    result = _base_result()

    result["smart_money_v2"] = {
        "structure": {
            "bos": False,
            "choch": False,
            "liquidity_sweep": False,
            "event": "RANGE",
            "direction": "RANGE",
        },
        "fvg": {
            "fvg": True,
            "direction": "BEARISH",
        },
        "order_block": {
            "order_block": False,
            "direction": "NONE",
        },
        "equal_levels": {
            "equal_highs": False,
            "equal_lows": False,
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

    assert capture.kwargs["fvg_score"] == 0.0, (
        "A BEARISH FVG must contribute zero directional "
        "FVG confirmation to an ALCISTA setup."
    )
