import pytest

from backend.signals.signal_generator_v2 import (
    SignalGeneratorV2,
)


def build_generator() -> SignalGeneratorV2:
    return SignalGeneratorV2(
        minimum_probability=0.80,
        minimum_confluence_score=0.80,
        allowed_grades={
            "A+",
            "A",
        },
    )


def build_valid_trade_plan() -> dict[str, object]:
    return {
        "approved": True,
        "status": "ACTIVE",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "risk_points": 5.0,
        "reward_points": 10.0,
        "reward_risk_ratio": 2.0,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "source_decision": "EXECUTE_LONG",
    }


def build_valid_validation() -> dict[str, object]:
    return {
        "approved": True,
        "status": "VALID",
        "decision": "ALLOW_EXECUTION",
        "blocking_reasons": [],
        "warnings": [],
    }


def test_generates_approved_long_signal():
    generator = build_generator()

    result = generator.generate(
        symbol="NQ",
        timeframe="5m",
        trade_plan=build_valid_trade_plan(),
        trade_validation=(
            build_valid_validation()
        ),
    )

    assert result["approved"] is True
    assert result["status"] == "READY"
    assert result["decision"] == "SEND_SIGNAL"
    assert result["symbol"] == "NQ"
    assert result["timeframe"] == "5M"
    assert result["direction"] == "LONG"
    assert result["entry_price"] == 100.0
    assert result["stop_loss"] == 95.0
    assert result["take_profit"] == 110.0
    assert result["contracts"] == 2
    assert result["probability"] == 0.92
    assert result["confluence_score"] == 0.90
    assert result["grade"] == "A+"
    assert result["blocking_reasons"] == []


def test_generates_approved_short_signal():
    generator = build_generator()

    trade_plan = build_valid_trade_plan()

    trade_plan.update(
        {
            "direction": "SHORT",
            "entry_price": 100.0,
            "stop_loss": 105.0,
            "take_profit": 90.0,
            "source_decision": (
                "EXECUTE_SHORT"
            ),
        }
    )

    result = generator.generate(
        symbol="MNQ",
        timeframe="1m",
        trade_plan=trade_plan,
        trade_validation=(
            build_valid_validation()
        ),
    )

    assert result["approved"] is True
    assert result["direction"] == "SHORT"
    assert result["decision"] == "SEND_SIGNAL"


def test_blocks_when_trade_plan_is_inactive():
    generator = build_generator()

    trade_plan = build_valid_trade_plan()
    trade_plan["approved"] = False
    trade_plan["status"] = "INACTIVE"

    result = generator.generate(
        symbol="NQ",
        timeframe="5m",
        trade_plan=trade_plan,
        trade_validation=(
            build_valid_validation()
        ),
    )

    assert result["approved"] is False
    assert result["status"] == "BLOCKED"
    assert result["decision"] == "DO_NOT_SEND"
    assert (
        "trade_plan_not_approved"
        in result["blocking_reasons"]
    )


def test_blocks_when_validation_rejects():
    generator = build_generator()

    validation = build_valid_validation()
    validation["approved"] = False
    validation["status"] = "INVALID"
    validation["decision"] = "BLOCK"
    validation["blocking_reasons"] = [
        "spread_too_high",
    ]

    result = generator.generate(
        symbol="NQ",
        timeframe="5m",
        trade_plan=build_valid_trade_plan(),
        trade_validation=validation,
    )

    assert result["approved"] is False
    assert result["decision"] == "DO_NOT_SEND"
    assert (
        "trade_validation_rejected"
        in result["blocking_reasons"]
    )
    assert (
        "spread_too_high"
        in result["blocking_reasons"]
    )


def test_blocks_probability_below_minimum():
    generator = build_generator()

    trade_plan = build_valid_trade_plan()
    trade_plan["probability"] = 0.70

    result = generator.generate(
        symbol="NQ",
        timeframe="5m",
        trade_plan=trade_plan,
        trade_validation=(
            build_valid_validation()
        ),
    )

    assert result["approved"] is False
    assert (
        "probability_below_minimum"
        in result["blocking_reasons"]
    )


def test_blocks_confluence_below_minimum():
    generator = build_generator()

    trade_plan = build_valid_trade_plan()
    trade_plan["confluence_score"] = 0.70

    result = generator.generate(
        symbol="NQ",
        timeframe="5m",
        trade_plan=trade_plan,
        trade_validation=(
            build_valid_validation()
        ),
    )

    assert result["approved"] is False
    assert (
        "confluence_below_minimum"
        in result["blocking_reasons"]
    )


def test_blocks_disallowed_grade():
    generator = build_generator()

    trade_plan = build_valid_trade_plan()
    trade_plan["grade"] = "B"

    result = generator.generate(
        symbol="NQ",
        timeframe="5m",
        trade_plan=trade_plan,
        trade_validation=(
            build_valid_validation()
        ),
    )

    assert result["approved"] is False
    assert (
        "grade_not_allowed"
        in result["blocking_reasons"]
    )


def test_preserves_validation_warnings():
    generator = build_generator()

    validation = build_valid_validation()
    validation["warnings"] = [
        "spread_near_limit",
    ]

    result = generator.generate(
        symbol="NQ",
        timeframe="5m",
        trade_plan=build_valid_trade_plan(),
        trade_validation=validation,
    )

    assert result["approved"] is True
    assert result["warnings"] == [
        "spread_near_limit",
    ]


def test_adds_signal_summary():
    generator = build_generator()

    result = generator.generate(
        symbol="NQ",
        timeframe="5m",
        trade_plan=build_valid_trade_plan(),
        trade_validation=(
            build_valid_validation()
        ),
    )

    summary = result["summary"]

    assert "NQ" in summary
    assert "LONG" in summary
    assert "100.0" in summary
    assert "95.0" in summary
    assert "110.0" in summary


def test_normalizes_symbol_timeframe_and_direction():
    generator = build_generator()

    trade_plan = build_valid_trade_plan()
    trade_plan["direction"] = " long "

    result = generator.generate(
        symbol=" nq ",
        timeframe=" 5m ",
        trade_plan=trade_plan,
        trade_validation=(
            build_valid_validation()
        ),
    )

    assert result["symbol"] == "NQ"
    assert result["timeframe"] == "5M"
    assert result["direction"] == "LONG"


def test_rejects_invalid_trade_plan_type():
    generator = build_generator()

    with pytest.raises(
        TypeError,
        match="trade_plan",
    ):
        generator.generate(
            symbol="NQ",
            timeframe="5m",
            trade_plan=object(),
            trade_validation=(
                build_valid_validation()
            ),
        )


def test_rejects_invalid_trade_validation_type():
    generator = build_generator()

    with pytest.raises(
        TypeError,
        match="trade_validation",
    ):
        generator.generate(
            symbol="NQ",
            timeframe="5m",
            trade_plan=build_valid_trade_plan(),
            trade_validation=object(),
        )


def test_rejects_empty_symbol():
    generator = build_generator()

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        generator.generate(
            symbol=" ",
            timeframe="5m",
            trade_plan=build_valid_trade_plan(),
            trade_validation=(
                build_valid_validation()
            ),
        )


def test_rejects_empty_timeframe():
    generator = build_generator()

    with pytest.raises(
        ValueError,
        match="timeframe",
    ):
        generator.generate(
            symbol="NQ",
            timeframe=" ",
            trade_plan=build_valid_trade_plan(),
            trade_validation=(
                build_valid_validation()
            ),
        )


def test_rejects_invalid_direction():
    generator = build_generator()

    trade_plan = build_valid_trade_plan()
    trade_plan["direction"] = "SIDEWAYS"

    with pytest.raises(
        ValueError,
        match="direction",
    ):
        generator.generate(
            symbol="NQ",
            timeframe="5m",
            trade_plan=trade_plan,
            trade_validation=(
                build_valid_validation()
            ),
        )


def test_rejects_invalid_probability():
    generator = build_generator()

    trade_plan = build_valid_trade_plan()
    trade_plan["probability"] = 1.1

    with pytest.raises(
        ValueError,
        match="probability",
    ):
        generator.generate(
            symbol="NQ",
            timeframe="5m",
            trade_plan=trade_plan,
            trade_validation=(
                build_valid_validation()
            ),
        )


def test_rejects_invalid_confluence_score():
    generator = build_generator()

    trade_plan = build_valid_trade_plan()
    trade_plan["confluence_score"] = -0.1

    with pytest.raises(
        ValueError,
        match="confluence_score",
    ):
        generator.generate(
            symbol="NQ",
            timeframe="5m",
            trade_plan=trade_plan,
            trade_validation=(
                build_valid_validation()
            ),
        )


def test_rejects_invalid_minimum_probability():
    with pytest.raises(
        ValueError,
        match="minimum_probability",
    ):
        SignalGeneratorV2(
            minimum_probability=1.1,
            minimum_confluence_score=0.80,
            allowed_grades={
                "A+",
                "A",
            },
        )


def test_rejects_empty_allowed_grades():
    with pytest.raises(
        ValueError,
        match="allowed_grades",
    ):
        SignalGeneratorV2(
            minimum_probability=0.80,
            minimum_confluence_score=0.80,
            allowed_grades=set(),
        )
