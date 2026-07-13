from backend.intelligence.confluence_engine import ConfluenceResult
from backend.intelligence.probability_engine import ProbabilityEngine


def test_high_quality_setup_is_approved() -> None:
    engine = ProbabilityEngine()

    confluence = ConfluenceResult(
        score=100.0,
        grade="A+",
        action="BUY",
        direction="BUY",
        approved=True,
        breakdown={
            "trend": 20.0,
            "ema": 15.0,
            "structure": 15.0,
            "bos": 15.0,
            "choch": 10.0,
            "liquidity": 10.0,
            "rsi": 5.0,
            "atr": 5.0,
            "risk": 5.0,
        },
    )

    result = engine.evaluate(confluence)

    assert result.probability >= 80.0
    assert result.confidence == "MUY ALTA"
    assert result.approved is True
    assert result.recommendation == "BUY"


def test_low_quality_setup_is_rejected() -> None:
    engine = ProbabilityEngine()

    confluence = ConfluenceResult(
        score=76.0,
        grade="C",
        action="NO_TRADE",
        direction="BUY",
        approved=False,
        breakdown={
            "trend": 20.0,
            "ema": 15.0,
            "structure": 15.0,
            "bos": 15.0,
            "choch": 5.0,
            "liquidity": 0.0,
            "rsi": 0.0,
            "atr": 1.0,
            "risk": 5.0,
        },
    )

    result = engine.evaluate(confluence)

    assert result.approved is False
    assert result.recommendation == "NO_TRADE"
    assert "No existe confirmación de liquidez" in result.negative_factors
    assert "RSI desfavorable o extremo" in result.negative_factors


def test_risk_rejection_blocks_operation() -> None:
    engine = ProbabilityEngine()

    confluence = ConfluenceResult(
        score=90.0,
        grade="A",
        action="NO_TRADE",
        direction="SELL",
        approved=False,
        breakdown={
            "trend": 20.0,
            "ema": 15.0,
            "structure": 15.0,
            "bos": 15.0,
            "choch": 10.0,
            "liquidity": 10.0,
            "rsi": 5.0,
            "atr": 5.0,
            "risk": 0.0,
        },
    )

    result = engine.evaluate(confluence)

    assert result.approved is False
    assert result.recommendation == "NO_TRADE"
    assert "Gestión de riesgo rechazada" in result.negative_factors