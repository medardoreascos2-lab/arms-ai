from backend.intelligence.trading_intelligence import TradingIntelligence


def test_bullish_conditions_generate_buy_recommendation():
    intelligence = TradingIntelligence()

    recommendation = intelligence.analyze(
        trend="ALCISTA",
        current_price=20100.0,
        ema=20000.0,
        rsi=55.0,
        rsi_status="NEUTRAL",
        atr=30.0,
        atr_status="VOLATILIDAD MEDIA",
        market_structure="ALCISTA",
        bos_detected="SÍ",
        bos_direction="ALCISTA",
        choch_detected="NO",
        choch_direction="NINGUNA",
    )

    assert recommendation == "BUSCAR COMPRAS"
    assert intelligence.score == 85
    assert intelligence.confidence == "ALTA"


def test_bearish_conditions_generate_sell_recommendation():
    intelligence = TradingIntelligence()

    recommendation = intelligence.analyze(
        trend="BAJISTA",
        current_price=19900.0,
        ema=20000.0,
        rsi=45.0,
        rsi_status="NEUTRAL",
        atr=30.0,
        atr_status="VOLATILIDAD MEDIA",
        market_structure="BAJISTA",
        bos_detected="SÍ",
        bos_direction="BAJISTA",
        choch_detected="NO",
        choch_direction="NINGUNA",
    )

    assert recommendation == "BUSCAR VENTAS"
    assert intelligence.score == -85
    assert intelligence.confidence == "ALTA"


def test_unclear_conditions_generate_wait_recommendation():
    intelligence = TradingIntelligence()

    recommendation = intelligence.analyze(
        trend="LATERAL",
        current_price=20000.0,
        ema=20000.0,
        rsi=50.0,
        rsi_status="NEUTRAL",
        atr=8.0,
        atr_status="VOLATILIDAD BAJA",
        market_structure="LATERAL",
        bos_detected="NO",
        bos_direction="NINGUNA",
        choch_detected="NO",
        choch_direction="NINGUNA",
    )

    assert recommendation == "ESPERAR"
    assert intelligence.score == 0
    assert intelligence.confidence == "BAJA"
