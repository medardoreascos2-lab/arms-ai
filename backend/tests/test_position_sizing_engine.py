import pytest

from backend.risk_management.position_sizing_engine import (
    PositionSizingEngine,
)


def build_engine() -> PositionSizingEngine:
    return PositionSizingEngine(
        minimum_contracts=1,
        maximum_contracts=20,
    )


def test_calculates_mnq_contracts():
    engine = build_engine()

    result = engine.calculate(
        account_balance=17000.0,
        risk_percent=0.5,
        entry_price=21691.0,
        stop_loss=21672.25,
        point_value=2.0,
    )

    assert result["approved"] is True
    assert result["contracts"] == 2
    assert result["risk_budget"] == 85.0
    assert result["stop_distance"] == 18.75
    assert result["risk_per_contract"] == 37.50
    assert result["planned_risk"] == 75.0
    assert result["remaining_risk"] == 10.0


def test_calculates_nq_contracts():
    engine = build_engine()

    result = engine.calculate(
        account_balance=150000.0,
        risk_percent=0.5,
        entry_price=21691.0,
        stop_loss=21672.25,
        point_value=20.0,
    )

    assert result["approved"] is True
    assert result["contracts"] == 2
    assert result["risk_budget"] == 750.0
    assert result["risk_per_contract"] == 375.0
    assert result["planned_risk"] == 750.0
    assert result["remaining_risk"] == 0.0


def test_supports_short_position():
    engine = build_engine()

    result = engine.calculate(
        account_balance=17000.0,
        risk_percent=0.5,
        entry_price=21691.0,
        stop_loss=21709.75,
        point_value=2.0,
    )

    assert result["approved"] is True
    assert result["stop_distance"] == 18.75
    assert result["contracts"] == 2


def test_blocks_when_risk_budget_cannot_cover_one_contract():
    engine = build_engine()

    result = engine.calculate(
        account_balance=1000.0,
        risk_percent=0.5,
        entry_price=21691.0,
        stop_loss=21672.25,
        point_value=20.0,
    )

    assert result["approved"] is False
    assert result["contracts"] == 0
    assert result["status"] == "INSUFFICIENT_RISK_BUDGET"
    assert result["risk_budget"] == 5.0
    assert result["risk_per_contract"] == 375.0


def test_limits_contracts_to_configured_maximum():
    engine = PositionSizingEngine(
        minimum_contracts=1,
        maximum_contracts=5,
    )

    result = engine.calculate(
        account_balance=150000.0,
        risk_percent=1.0,
        entry_price=21691.0,
        stop_loss=21690.0,
        point_value=2.0,
    )

    assert result["approved"] is True
    assert result["contracts"] == 5
    assert result["status"] == "CAPPED_AT_MAXIMUM"


def test_reports_standard_approval_status():
    engine = build_engine()

    result = engine.calculate(
        account_balance=17000.0,
        risk_percent=0.5,
        entry_price=21691.0,
        stop_loss=21672.25,
        point_value=2.0,
    )

    assert result["status"] == "APPROVED"


def test_rejects_zero_account_balance():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="account_balance",
    ):
        engine.calculate(
            account_balance=0,
            risk_percent=0.5,
            entry_price=21691.0,
            stop_loss=21672.25,
            point_value=2.0,
        )


def test_rejects_zero_risk_percent():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="risk_percent",
    ):
        engine.calculate(
            account_balance=17000.0,
            risk_percent=0,
            entry_price=21691.0,
            stop_loss=21672.25,
            point_value=2.0,
        )


def test_rejects_risk_percent_above_one_hundred():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="risk_percent",
    ):
        engine.calculate(
            account_balance=17000.0,
            risk_percent=101.0,
            entry_price=21691.0,
            stop_loss=21672.25,
            point_value=2.0,
        )


def test_rejects_zero_stop_distance():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="stop_distance",
    ):
        engine.calculate(
            account_balance=17000.0,
            risk_percent=0.5,
            entry_price=21691.0,
            stop_loss=21691.0,
            point_value=2.0,
        )


def test_rejects_invalid_point_value():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="point_value",
    ):
        engine.calculate(
            account_balance=17000.0,
            risk_percent=0.5,
            entry_price=21691.0,
            stop_loss=21672.25,
            point_value=0,
        )


def test_rejects_invalid_minimum_contracts():
    with pytest.raises(
        ValueError,
        match="minimum_contracts",
    ):
        PositionSizingEngine(
            minimum_contracts=0,
            maximum_contracts=20,
        )


def test_rejects_maximum_below_minimum():
    with pytest.raises(
        ValueError,
        match="maximum_contracts",
    ):
        PositionSizingEngine(
            minimum_contracts=5,
            maximum_contracts=2,
        )
