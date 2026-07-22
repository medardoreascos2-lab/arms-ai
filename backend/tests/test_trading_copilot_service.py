from types import SimpleNamespace

import pytest

from backend.ai.trading.trading_copilot_service import (
    TradingCopilotService,
)


def build_context() -> dict[str, object]:
    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "current_price": 21624.50,
        "ema": SimpleNamespace(
            ema=21610.25,
            period=50,
        ),
        "rsi": SimpleNamespace(
            rsi=57.40,
            status="NEUTRAL",
        ),
        "atr": SimpleNamespace(
            atr=12.50,
            status="ADECUADO",
        ),
        "trend": SimpleNamespace(
            trend="ALCISTA",
        ),
        "market_structure": SimpleNamespace(
            structure="ALCISTA",
            last_high_type="HH",
            last_low_type="HL",
        ),
        "bos": SimpleNamespace(
            bos="SÍ",
            direction="ALCISTA",
        ),
        "choch": SimpleNamespace(
            choch="NO",
            direction="NINGUNA",
        ),
        "liquidity": SimpleNamespace(
            equal_highs=False,
            equal_lows=True,
            sweep_detected="SÍ",
            sweep_direction="ALCISTA",
            liquidity_level=21600.00,
        ),
        "confluence_result": SimpleNamespace(
            score=87.0,
            grade="A+",
            action="BUY",
            direction="BUY",
            approved=True,
            confirmations=[
                "Tendencia alineada",
                "Estructura confirmada",
            ],
            warnings=[],
        ),
        "probability_result": SimpleNamespace(
            probability=84.0,
            confidence="MUY ALTA",
            approved=True,
            recommendation="BUY",
            positive_factors=[
                "Tendencia principal alineada",
            ],
            negative_factors=[],
        ),
        "validator": SimpleNamespace(
            is_valid=True,
        ),
        "dynamic_risk": SimpleNamespace(
            risk_amount=85.0,
            stop_distance=18.75,
            take_profit_distance=37.50,
            contracts=2,
        ),
        "trade_levels": SimpleNamespace(
            entry_price=21624.50,
            stop_loss=21605.75,
            take_profit=21662.00,
        ),
    }


def test_builds_trading_copilot_context():
    result = TradingCopilotService().build_context(
        build_context()
    )

    assert result["symbol"] == "NQ"
    assert result["timeframe"] == "5m"
    assert result["current_price"] == 21624.50

    assert result["trend"] == "ALCISTA"
    assert result["indicators"]["ema"] == 21610.25
    assert result["indicators"]["rsi"] == 57.40
    assert result["indicators"]["atr"] == 12.50

    assert result["market_structure"]["direction"] == "ALCISTA"
    assert result["market_structure"]["high_type"] == "HH"
    assert result["market_structure"]["low_type"] == "HL"

    assert result["smart_money"]["bos"]["detected"] is True
    assert result["smart_money"]["bos"]["direction"] == "ALCISTA"

    assert result["smart_money"]["choch"]["detected"] is False
    assert result["smart_money"]["liquidity"]["detected"] is True
    assert (
        result["smart_money"]["liquidity"]["direction"]
        == "ALCISTA"
    )

    assert result["decision"]["score"] == 87.0
    assert result["decision"]["grade"] == "A+"
    assert result["decision"]["action"] == "BUY"
    assert result["decision"]["approved"] is True

    assert result["probability"]["value"] == 84.0
    assert result["probability"]["confidence"] == "MUY ALTA"
    assert result["probability"]["approved"] is True

    assert result["risk"]["approved"] is True
    assert result["risk"]["risk_amount"] == 85.0
    assert result["risk"]["contracts"] == 2

    assert result["trade"]["entry_price"] == 21624.50
    assert result["trade"]["stop_loss"] == 21605.75
    assert result["trade"]["take_profit"] == 21662.00


def test_rejects_missing_required_context():
    context = build_context()
    context.pop("trend")

    with pytest.raises(
        KeyError,
        match="trend",
    ):
        TradingCopilotService().build_context(
            context
        )


def test_normalizes_boolean_signals():
    context = build_context()

    context["bos"].bos = True
    context["choch"].choch = False
    context["liquidity"].sweep_detected = "NO"

    result = TradingCopilotService().build_context(
        context
    )

    assert result["smart_money"]["bos"]["detected"] is True
    assert result["smart_money"]["choch"]["detected"] is False
    assert (
        result["smart_money"]["liquidity"]["detected"]
        is False
    )
