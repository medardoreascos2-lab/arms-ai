import pytest

from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)


def build_engine():
    return PositionSizingEngineV2()


def test_calculates_contracts():

    engine = build_engine()

    result = engine.calculate(
        account_balance=17000.0,
        risk_percent=0.5,
        stop_points=20.0,
        point_value=2.0,
    )

    assert result["approved"] is True
    assert result["risk_amount"] == 85.0
    assert result["contracts"] == 2
    assert result["actual_risk"] == 80.0
    assert result["remaining_risk"] == 5.0


def test_rounds_down_contracts():

    engine = build_engine()

    result = engine.calculate(
        account_balance=10000.0,
        risk_percent=1.0,
        stop_points=17.0,
        point_value=2.0,
    )

    assert result["contracts"] == 2


def test_rejects_zero_balance():

    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="account_balance",
    ):
        engine.calculate(
            account_balance=0.0,
            risk_percent=1.0,
            stop_points=20.0,
            point_value=2.0,
        )


def test_rejects_invalid_risk():

    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="risk_percent",
    ):
        engine.calculate(
            account_balance=10000.0,
            risk_percent=0.0,
            stop_points=20.0,
            point_value=2.0,
        )


def test_rejects_invalid_stop():

    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="stop_points",
    ):
        engine.calculate(
            account_balance=10000.0,
            risk_percent=1.0,
            stop_points=0.0,
            point_value=2.0,
        )


def test_rejects_invalid_point_value():

    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="point_value",
    ):
        engine.calculate(
            account_balance=10000.0,
            risk_percent=1.0,
            stop_points=20.0,
            point_value=0.0,
        )


def test_returns_not_approved_when_no_contracts():

    engine = build_engine()

    result = engine.calculate(
        account_balance=500.0,
        risk_percent=0.25,
        stop_points=100.0,
        point_value=20.0,
    )

    assert result["approved"] is False
    assert result["contracts"] == 0
    assert result["reason"] == "risk_too_small"
