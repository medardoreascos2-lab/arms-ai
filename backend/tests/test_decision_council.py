from backend.intelligence.confluence_engine import ConfluenceResult
from backend.intelligence.probability_engine import ProbabilityResult
from backend.models.reasoning_result import ReasoningResult
from backend.intelligence.decision_council import DecisionCouncil


def test_decision_council_approves_a_plus_trade():
    council = DecisionCouncil()

    confluence = ConfluenceResult(
        score=96.0,
        grade="A+",
        action="BUY",
        direction="BUY",
        approved=True,
        confirmations=["Confluencia fuerte."],
        warnings=[],
        breakdown={},
    )

    probability = ProbabilityResult(
        probability=84.0,
        confidence="MUY ALTA",
        approved=True,
        recommendation="BUY",
        positive_factors=["Probabilidad suficiente."],
        negative_factors=[],
        adjustments={},
    )

    reasoning = ReasoningResult(
        direction="COMPRA",
        grade="A+",
        buy_score=90,
        sell_score=15,
        quality_score=90,
        confidence="ALTA",
        authorized=True,
        reasons=["Razonamiento alineado."],
        blockers=[],
    )

    result = council.evaluate(
        confluence=confluence,
        probability=probability,
        reasoning=reasoning,
        risk_allowed=True,
        session_allowed=True,
    )

    assert result.approved is True
    assert result.action == "BUY"
    assert result.direction == "BUY"
    assert result.grade == "A+"
    assert result.votes_for >= 3
    assert result.votes_against == 0


def test_decision_council_blocks_trade_when_risk_is_not_allowed():
    council = DecisionCouncil()

    confluence = ConfluenceResult(
        score=96.0,
        grade="A+",
        action="BUY",
        direction="BUY",
        approved=True,
        confirmations=[],
        warnings=[],
        breakdown={},
    )

    probability = ProbabilityResult(
        probability=84.0,
        confidence="MUY ALTA",
        approved=True,
        recommendation="BUY",
        positive_factors=[],
        negative_factors=[],
        adjustments={},
    )

    reasoning = ReasoningResult(
        direction="COMPRA",
        grade="A+",
        buy_score=90,
        sell_score=15,
        quality_score=90,
        confidence="ALTA",
        authorized=True,
        reasons=[],
        blockers=[],
    )

    result = council.evaluate(
        confluence=confluence,
        probability=probability,
        reasoning=reasoning,
        risk_allowed=False,
        session_allowed=True,
    )

    assert result.approved is False
    assert result.action == "NO_TRADE"
    assert "Riesgo no autorizado." in result.blockers


def test_decision_council_rejects_direction_conflict():
    council = DecisionCouncil()

    confluence = ConfluenceResult(
        score=92.0,
        grade="A",
        action="BUY",
        direction="BUY",
        approved=True,
        confirmations=[],
        warnings=[],
        breakdown={},
    )

    probability = ProbabilityResult(
        probability=78.0,
        confidence="ALTA",
        approved=True,
        recommendation="BUY",
        positive_factors=[],
        negative_factors=[],
        adjustments={},
    )

    reasoning = ReasoningResult(
        direction="VENTA",
        grade="A",
        buy_score=20,
        sell_score=80,
        quality_score=80,
        confidence="MEDIA",
        authorized=True,
        reasons=[],
        blockers=[],
    )

    result = council.evaluate(
        confluence=confluence,
        probability=probability,
        reasoning=reasoning,
        risk_allowed=True,
        session_allowed=True,
    )

    assert result.approved is False
    assert result.action == "NO_TRADE"
    assert result.votes_against >= 1
    assert "Conflicto de dirección entre motores." in result.blockers


def test_decision_council_preserves_diagnostics_when_risk_blocks_trade():
    council = DecisionCouncil()

    confluence = ConfluenceResult(
        score=71.0,
        grade="C",
        action="NO_TRADE",
        direction="BUY",
        approved=False,
        confirmations=["Tendencia alineada."],
        warnings=["No existe confirmación de liquidez."],
        breakdown={},
    )

    probability = ProbabilityResult(
        probability=23.0,
        confidence="BAJA",
        approved=False,
        recommendation="NO_TRADE",
        positive_factors=["Estructura confirmada."],
        negative_factors=["Volatilidad inadecuada."],
        adjustments={},
    )

    reasoning = ReasoningResult(
        direction="COMPRA",
        grade="A",
        buy_score=70,
        sell_score=15,
        quality_score=70,
        confidence="MEDIA",
        authorized=False,
        reasons=["Sesgo técnico comprador."],
        blockers=["Volatilidad insuficiente."],
    )

    result = council.evaluate(
        confluence=confluence,
        probability=probability,
        reasoning=reasoning,
        risk_allowed=False,
        session_allowed=True,
    )

    assert result.approved is False
    assert "Riesgo no autorizado." in result.blockers
    assert "Volatilidad insuficiente." in result.blockers
    assert "No existe confirmación de liquidez." in result.warnings
    assert "Volatilidad inadecuada." in result.warnings
