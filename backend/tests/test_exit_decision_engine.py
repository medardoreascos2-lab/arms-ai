import pytest

from backend.execution.exit_decision_engine import (
    ExitDecisionEngine,
)


def build_engine() -> ExitDecisionEngine:
    return ExitDecisionEngine(
        hold_momentum_threshold=0.30,
        exit_momentum_threshold=-0.30,
        protect_min_profit_points=10.0,
    )


def test_holds_when_momentum_is_strong():
    engine = build_engine()

    result = engine.evaluate(
        directional_momentum=0.75,
        unrealized_points=25.0,
        adverse_structure=False,
    )

    assert result["decision"] == "HOLD"
    assert result["confidence"] == 0.75
    assert result["reason"] == "Momentum favorable"


def test_holds_profitable_trade_without_adverse_structure():
    engine = build_engine()

    result = engine.evaluate(
        directional_momentum=0.20,
        unrealized_points=8.0,
        adverse_structure=False,
    )

    assert result["decision"] == "HOLD"
    assert result["reason"] == "Sin confirmación de salida"


def test_protects_profit_when_momentum_weakens():
    engine = build_engine()

    result = engine.evaluate(
        directional_momentum=0.10,
        unrealized_points=30.0,
        adverse_structure=False,
    )

    assert result["decision"] == "PROTECT"
    assert result["confidence"] == 0.90
    assert result["reason"] == "Momentum debilitándose con ganancia"


def test_protects_when_structure_turns_adverse_but_momentum_not_critical():
    engine = build_engine()

    result = engine.evaluate(
        directional_momentum=-0.10,
        unrealized_points=20.0,
        adverse_structure=True,
    )

    assert result["decision"] == "PROTECT"
    assert result["reason"] == "Estructura adversa con ganancia"


def test_exits_when_structure_and_momentum_are_adverse():
    engine = build_engine()

    result = engine.evaluate(
        directional_momentum=-0.70,
        unrealized_points=5.0,
        adverse_structure=True,
    )

    assert result["decision"] == "EXIT"
    assert result["confidence"] == 0.70
    assert result["reason"] == "Momentum contrario y estructura adversa"


def test_does_not_exit_only_for_negative_momentum():
    engine = build_engine()

    result = engine.evaluate(
        directional_momentum=-0.50,
        unrealized_points=-10.0,
        adverse_structure=False,
    )

    assert result["decision"] == "HOLD"
    assert result["reason"] == "Sin confirmación de salida"


def test_confidence_is_always_between_zero_and_one():
    engine = build_engine()

    result = engine.evaluate(
        directional_momentum=1.0,
        unrealized_points=50.0,
        adverse_structure=False,
    )

    assert 0.0 <= result["confidence"] <= 1.0


def test_rejects_momentum_above_one():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="directional_momentum",
    ):
        engine.evaluate(
            directional_momentum=1.1,
            unrealized_points=10.0,
            adverse_structure=False,
        )


def test_rejects_momentum_below_minus_one():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="directional_momentum",
    ):
        engine.evaluate(
            directional_momentum=-1.1,
            unrealized_points=10.0,
            adverse_structure=False,
        )


def test_rejects_invalid_hold_threshold():
    with pytest.raises(
        ValueError,
        match="hold_momentum_threshold",
    ):
        ExitDecisionEngine(
            hold_momentum_threshold=1.5,
            exit_momentum_threshold=-0.30,
            protect_min_profit_points=10.0,
        )


def test_rejects_invalid_exit_threshold():
    with pytest.raises(
        ValueError,
        match="exit_momentum_threshold",
    ):
        ExitDecisionEngine(
            hold_momentum_threshold=0.30,
            exit_momentum_threshold=0.50,
            protect_min_profit_points=10.0,
        )


def test_rejects_negative_protect_profit():
    with pytest.raises(
        ValueError,
        match="protect_min_profit_points",
    ):
        ExitDecisionEngine(
            hold_momentum_threshold=0.30,
            exit_momentum_threshold=-0.30,
            protect_min_profit_points=-1.0,
        )
