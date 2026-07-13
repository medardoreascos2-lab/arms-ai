from backend.intelligence.reasoning_engine import ReasoningEngine


def test_reasoning_engine_approves_a_plus_buy_setup():
    engine = ReasoningEngine()

    result = engine.evaluate(
        trend="ALCISTA",
        market_structure="ALCISTA",
        bos_direction="ALCISTA",
        choch_direction="NINGUNA",
        liquidity_confirmed=True,
        rsi_status="NEUTRAL",
        atr_status="VOLATILIDAD MEDIA",
        reward_risk_ratio=3.0,
        risk_allowed=True,
        session_allowed=True,
    )

    assert result.direction == "COMPRA"
    assert result.grade == "A+"
    assert result.authorized is True
    assert result.confidence == "ALTA"
    assert result.buy_score > result.sell_score


def test_reasoning_engine_blocks_authorization_when_risk_is_not_allowed():
    engine = ReasoningEngine()

    result = engine.evaluate(
        trend="ALCISTA",
        market_structure="ALCISTA",
        bos_direction="ALCISTA",
        choch_direction="NINGUNA",
        liquidity_confirmed=True,
        rsi_status="NEUTRAL",
        atr_status="VOLATILIDAD MEDIA",
        reward_risk_ratio=3.0,
        risk_allowed=False,
        session_allowed=True,
    )

    assert result.direction == "COMPRA"
    assert result.grade == "A+"
    assert result.authorized is False
    assert result.quality_score >= 85
    assert "Riesgo no autorizado." in result.blockers


def test_reasoning_engine_waits_when_confluence_is_insufficient():
    engine = ReasoningEngine()

    result = engine.evaluate(
        trend="LATERAL",
        market_structure="LATERAL",
        bos_direction="NINGUNA",
        choch_direction="NINGUNA",
        liquidity_confirmed=False,
        rsi_status="NEUTRAL",
        atr_status="VOLATILIDAD BAJA",
        reward_risk_ratio=1.2,
        risk_allowed=True,
        session_allowed=True,
    )

    assert result.direction == "ESPERAR"
    assert result.grade == "NO OPERAR"
    assert result.authorized is False
    assert result.quality_score < 70
    assert "Volatilidad insuficiente." in result.blockers
    assert (
        "Relación riesgo/beneficio insuficiente."
        in result.blockers
    )


def test_reasoning_engine_keeps_technical_score_when_risk_blocks_trade():
    engine = ReasoningEngine()

    result = engine.evaluate(
        trend="ALCISTA",
        market_structure="ALCISTA",
        bos_direction="ALCISTA",
        choch_direction="NINGUNA",
        liquidity_confirmed=True,
        rsi_status="NEUTRAL",
        atr_status="VOLATILIDAD MEDIA",
        reward_risk_ratio=3.0,
        risk_allowed=False,
        session_allowed=True,
    )

    assert result.authorized is False
    assert result.direction == "COMPRA"
    assert result.quality_score >= 85
    assert "Riesgo no autorizado." in result.blockers
