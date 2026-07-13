from backend.intelligence.confluence_engine import ConfluenceEngine


def test_bullish_a_plus_setup() -> None:
    engine = ConfluenceEngine()

    result = engine.evaluate(
        trend="BULLISH",
        ema="BULLISH",
        rsi=55.0,
        atr={"status": "NORMAL"},
        structure="BULLISH",
        bos="BULLISH",
        choch="BULLISH",
        liquidity={
            "sweep_detected": True,
            "direction": "BULLISH",
        },
        risk={"approved": True},
    )

    assert result.score == 100.0
    assert result.grade == "A+"
    assert result.direction == "BUY"
    assert result.action == "BUY"
    assert result.approved is True


def test_trade_is_blocked_when_risk_is_not_approved() -> None:
    engine = ConfluenceEngine()

    result = engine.evaluate(
        trend="BULLISH",
        ema="BULLISH",
        rsi=55.0,
        atr={"status": "NORMAL"},
        structure="BULLISH",
        bos="BULLISH",
        choch="BULLISH",
        liquidity={
            "sweep_detected": True,
            "direction": "BULLISH",
        },
        risk={"approved": False},
    )

    assert result.score == 95.0
    assert result.grade == "A+"
    assert result.direction == "BUY"
    assert result.action == "NO_TRADE"
    assert result.approved is False


def test_conflicting_signals_produce_no_trade() -> None:
    engine = ConfluenceEngine()

    result = engine.evaluate(
        trend="BULLISH",
        ema="BEARISH",
        rsi=70.0,
        atr={"status": "LOW"},
        structure="NEUTRAL",
        bos="NEUTRAL",
        choch="BEARISH",
        liquidity=False,
        risk={"approved": True},
    )

    assert result.action == "NO_TRADE"
    assert result.approved is False