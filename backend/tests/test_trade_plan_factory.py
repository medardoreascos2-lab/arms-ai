from backend.models.decision_council_result import DecisionCouncilResult
from backend.services.trade_plan_factory import TradePlanFactory


def test_factory_builds_authorized_buy_trade_plan():
    factory = TradePlanFactory()

    council_result = DecisionCouncilResult(
        action="BUY",
        direction="BUY",
        grade="A+",
        approved=True,
        probability=84.0,
        confidence="MUY ALTA",
        confluence_score=96.0,
        reasoning_score=90,
        votes_for=3,
        votes_against=0,
        reasons=["Configuración A+."],
        blockers=[],
        warnings=[],
    )

    trade_plan = factory.create(
        symbol="NASDAQ / NQ",
        timeframe="1m",
        council_result=council_result,
        entry_price=21624.50,
        stop_loss=21618.00,
        take_profit=21637.50,
        contracts=2,
        risk_amount=85.0,
    )

    assert trade_plan.decision == "BUY"
    assert trade_plan.confidence == "MUY ALTA"
    assert trade_plan.authorized is True
    assert trade_plan.contracts == 2
    assert trade_plan.entry_price == 21624.50
    assert "Configuración A+." in trade_plan.reasons


def test_factory_builds_safe_blocked_trade_plan():
    factory = TradePlanFactory()

    council_result = DecisionCouncilResult(
        action="NO_TRADE",
        direction="NEUTRAL",
        grade="NO OPERAR",
        approved=False,
        probability=23.0,
        confidence="BAJA",
        confluence_score=71.0,
        reasoning_score=70,
        votes_for=0,
        votes_against=1,
        reasons=[],
        blockers=["Riesgo no autorizado."],
        warnings=["Volatilidad insuficiente."],
    )

    trade_plan = factory.create(
        symbol="NASDAQ / NQ",
        timeframe="1m",
        council_result=council_result,
        entry_price=21624.50,
        stop_loss=21618.00,
        take_profit=21637.50,
        contracts=6,
        risk_amount=85.0,
    )

    assert trade_plan.decision == "NO_TRADE"
    assert trade_plan.confidence == "BAJA"
    assert trade_plan.authorized is False
    assert trade_plan.contracts == 0
    assert trade_plan.entry_price is None
    assert trade_plan.stop_loss is None
    assert trade_plan.take_profit is None
    assert trade_plan.risk_amount == 0.0
    assert "Riesgo no autorizado." in trade_plan.reasons
    assert "Volatilidad insuficiente." in trade_plan.reasons
