import pytest

from backend.execution.portfolio_risk_engine_v2 import (
    PortfolioRiskEngineV2,
)


def build_engine() -> PortfolioRiskEngineV2:
    return PortfolioRiskEngineV2(
        maximum_total_open_risk=1000.0,
        maximum_floating_loss=600.0,
        maximum_long_risk=700.0,
        maximum_short_risk=700.0,
        maximum_symbol_risk=500.0,
    )


def build_positions() -> list[dict[str, object]]:
    return [
        {
            "position_id": "position-001",
            "symbol": "NQ",
            "status": "OPEN",
            "direction": "LONG",
            "quantity": 2,
            "entry_price": 100.0,
            "current_price": 105.0,
            "stop_loss": 90.0,
            "point_value": 2.0,
        },
        {
            "position_id": "position-002",
            "symbol": "ES",
            "status": "OPEN",
            "direction": "SHORT",
            "quantity": 1,
            "entry_price": 100.0,
            "current_price": 96.0,
            "stop_loss": 110.0,
            "point_value": 5.0,
        },
    ]


def test_calculates_portfolio_risk():
    engine = build_engine()

    result = engine.evaluate(
        open_positions=build_positions(),
        candidate_symbol="MNQ",
        candidate_direction="LONG",
        candidate_contracts=2,
        candidate_entry_price=100.0,
        candidate_current_price=100.0,
        candidate_stop_loss=90.0,
        candidate_point_value=2.0,
    )

    assert result["approved"] is True

    assert (
        result["current_total_open_risk"]
        == 90.0
    )

    assert (
        result["current_long_risk"]
        == 40.0
    )

    assert (
        result["current_short_risk"]
        == 50.0
    )

    assert (
        result["candidate_risk"]
        == 40.0
    )

    assert (
        result["projected_total_open_risk"]
        == 130.0
    )


def test_calculates_floating_pnl():
    engine = build_engine()

    result = engine.evaluate(
        open_positions=build_positions(),
        candidate_symbol="MNQ",
        candidate_direction="LONG",
        candidate_contracts=1,
        candidate_entry_price=100.0,
        candidate_current_price=100.0,
        candidate_stop_loss=90.0,
        candidate_point_value=2.0,
    )

    assert (
        result["current_floating_pnl"]
        == 40.0
    )

    assert (
        result["current_floating_loss"]
        == 0.0
    )


def test_calculates_floating_loss():
    engine = build_engine()

    positions = [
        {
            "position_id": "position-001",
            "symbol": "NQ",
            "status": "OPEN",
            "direction": "LONG",
            "quantity": 2,
            "entry_price": 100.0,
            "current_price": 90.0,
            "stop_loss": 80.0,
            "point_value": 2.0,
        },
    ]

    result = engine.evaluate(
        open_positions=positions,
        candidate_symbol="ES",
        candidate_direction="SHORT",
        candidate_contracts=1,
        candidate_entry_price=100.0,
        candidate_current_price=100.0,
        candidate_stop_loss=110.0,
        candidate_point_value=5.0,
    )

    assert (
        result["current_floating_pnl"]
        == -40.0
    )

    assert (
        result["current_floating_loss"]
        == 40.0
    )


def test_blocks_total_open_risk():
    engine = PortfolioRiskEngineV2(
        maximum_total_open_risk=100.0,
        maximum_floating_loss=600.0,
        maximum_long_risk=100.0,
        maximum_short_risk=100.0,
        maximum_symbol_risk=100.0,
    )

    result = engine.evaluate(
        open_positions=build_positions(),
        candidate_symbol="NQ",
        candidate_direction="LONG",
        candidate_contracts=2,
        candidate_entry_price=100.0,
        candidate_current_price=100.0,
        candidate_stop_loss=90.0,
        candidate_point_value=2.0,
    )

    assert result["approved"] is False

    assert (
        "maximum_total_open_risk_exceeded"
        in result["blocking_reasons"]
    )


def test_blocks_floating_loss():
    engine = PortfolioRiskEngineV2(
        maximum_total_open_risk=1000.0,
        maximum_floating_loss=30.0,
        maximum_long_risk=700.0,
        maximum_short_risk=700.0,
        maximum_symbol_risk=500.0,
    )

    positions = [
        {
            "position_id": "position-001",
            "symbol": "NQ",
            "status": "OPEN",
            "direction": "LONG",
            "quantity": 2,
            "entry_price": 100.0,
            "current_price": 90.0,
            "stop_loss": 80.0,
            "point_value": 2.0,
        },
    ]

    result = engine.evaluate(
        open_positions=positions,
        candidate_symbol="ES",
        candidate_direction="SHORT",
        candidate_contracts=1,
        candidate_entry_price=100.0,
        candidate_current_price=100.0,
        candidate_stop_loss=110.0,
        candidate_point_value=5.0,
    )

    assert result["approved"] is False

    assert (
        "maximum_floating_loss_exceeded"
        in result["blocking_reasons"]
    )


def test_blocks_long_risk():
    engine = PortfolioRiskEngineV2(
        maximum_total_open_risk=1000.0,
        maximum_floating_loss=600.0,
        maximum_long_risk=50.0,
        maximum_short_risk=700.0,
        maximum_symbol_risk=500.0,
    )

    result = engine.evaluate(
        open_positions=[],
        candidate_symbol="NQ",
        candidate_direction="LONG",
        candidate_contracts=3,
        candidate_entry_price=100.0,
        candidate_current_price=100.0,
        candidate_stop_loss=90.0,
        candidate_point_value=2.0,
    )

    assert result["approved"] is False

    assert (
        "maximum_long_risk_exceeded"
        in result["blocking_reasons"]
    )


def test_blocks_short_risk():
    engine = PortfolioRiskEngineV2(
        maximum_total_open_risk=1000.0,
        maximum_floating_loss=600.0,
        maximum_long_risk=700.0,
        maximum_short_risk=50.0,
        maximum_symbol_risk=500.0,
    )

    result = engine.evaluate(
        open_positions=[],
        candidate_symbol="NQ",
        candidate_direction="SHORT",
        candidate_contracts=3,
        candidate_entry_price=100.0,
        candidate_current_price=100.0,
        candidate_stop_loss=110.0,
        candidate_point_value=2.0,
    )

    assert result["approved"] is False

    assert (
        "maximum_short_risk_exceeded"
        in result["blocking_reasons"]
    )


def test_blocks_symbol_risk():
    engine = PortfolioRiskEngineV2(
        maximum_total_open_risk=1000.0,
        maximum_floating_loss=600.0,
        maximum_long_risk=700.0,
        maximum_short_risk=700.0,
        maximum_symbol_risk=50.0,
    )

    result = engine.evaluate(
        open_positions=[],
        candidate_symbol="NQ",
        candidate_direction="LONG",
        candidate_contracts=3,
        candidate_entry_price=100.0,
        candidate_current_price=100.0,
        candidate_stop_loss=90.0,
        candidate_point_value=2.0,
    )

    assert result["approved"] is False

    assert (
        "maximum_symbol_risk_exceeded"
        in result["blocking_reasons"]
    )


def test_ignores_closed_positions():
    engine = build_engine()

    positions = [
        {
            "position_id": "position-001",
            "symbol": "NQ",
            "status": "CLOSED",
            "direction": "LONG",
            "quantity": 100,
            "entry_price": 100.0,
            "current_price": 1.0,
            "stop_loss": 1.0,
            "point_value": 20.0,
        },
    ]

    result = engine.evaluate(
        open_positions=positions,
        candidate_symbol="ES",
        candidate_direction="LONG",
        candidate_contracts=1,
        candidate_entry_price=100.0,
        candidate_current_price=100.0,
        candidate_stop_loss=90.0,
        candidate_point_value=2.0,
    )

    assert result["approved"] is True
    assert result["current_total_open_risk"] == 0.0
    assert result["current_floating_pnl"] == 0.0


def test_normalizes_symbol_and_direction():
    engine = build_engine()

    result = engine.evaluate(
        open_positions=[],
        candidate_symbol=" nq ",
        candidate_direction=" long ",
        candidate_contracts=1,
        candidate_entry_price=100.0,
        candidate_current_price=100.0,
        candidate_stop_loss=90.0,
        candidate_point_value=2.0,
    )

    assert result["candidate_symbol"] == "NQ"
    assert result["candidate_direction"] == "LONG"


def test_returns_remaining_capacities():
    engine = build_engine()

    result = engine.evaluate(
        open_positions=[],
        candidate_symbol="NQ",
        candidate_direction="LONG",
        candidate_contracts=2,
        candidate_entry_price=100.0,
        candidate_current_price=100.0,
        candidate_stop_loss=90.0,
        candidate_point_value=2.0,
    )

    assert (
        result["remaining_total_open_risk_capacity"]
        == 960.0
    )

    assert (
        result["remaining_direction_risk_capacity"]
        == 660.0
    )

    assert (
        result["remaining_symbol_risk_capacity"]
        == 460.0
    )


def test_rejects_invalid_open_positions_type():
    engine = build_engine()

    with pytest.raises(
        TypeError,
        match="open_positions",
    ):
        engine.evaluate(
            open_positions=object(),
            candidate_symbol="NQ",
            candidate_direction="LONG",
            candidate_contracts=1,
            candidate_entry_price=100.0,
            candidate_current_price=100.0,
            candidate_stop_loss=90.0,
            candidate_point_value=2.0,
        )


def test_rejects_invalid_position_item():
    engine = build_engine()

    with pytest.raises(
        TypeError,
        match="position",
    ):
        engine.evaluate(
            open_positions=[
                object(),
            ],
            candidate_symbol="NQ",
            candidate_direction="LONG",
            candidate_contracts=1,
            candidate_entry_price=100.0,
            candidate_current_price=100.0,
            candidate_stop_loss=90.0,
            candidate_point_value=2.0,
        )


def test_rejects_invalid_direction():
    engine = build_engine()

    with pytest.raises(
        ValueError,
        match="candidate_direction",
    ):
        engine.evaluate(
            open_positions=[],
            candidate_symbol="NQ",
            candidate_direction="SIDEWAYS",
            candidate_contracts=1,
            candidate_entry_price=100.0,
            candidate_current_price=100.0,
            candidate_stop_loss=90.0,
            candidate_point_value=2.0,
        )


@pytest.mark.parametrize(
    (
        "parameter",
        "value",
    ),
    [
        (
            "candidate_contracts",
            0,
        ),
        (
            "candidate_entry_price",
            0.0,
        ),
        (
            "candidate_current_price",
            0.0,
        ),
        (
            "candidate_stop_loss",
            0.0,
        ),
        (
            "candidate_point_value",
            0.0,
        ),
    ],
)
def test_rejects_invalid_candidate_values(
    parameter,
    value,
):
    engine = build_engine()

    arguments = {
        "open_positions": [],
        "candidate_symbol": "NQ",
        "candidate_direction": "LONG",
        "candidate_contracts": 1,
        "candidate_entry_price": 100.0,
        "candidate_current_price": 100.0,
        "candidate_stop_loss": 90.0,
        "candidate_point_value": 2.0,
    }

    arguments[
        parameter
    ] = value

    with pytest.raises(
        ValueError,
        match=parameter,
    ):
        engine.evaluate(
            **arguments,
        )


@pytest.mark.parametrize(
    (
        "parameter",
        "value",
    ),
    [
        (
            "maximum_total_open_risk",
            0.0,
        ),
        (
            "maximum_floating_loss",
            0.0,
        ),
        (
            "maximum_long_risk",
            0.0,
        ),
        (
            "maximum_short_risk",
            0.0,
        ),
        (
            "maximum_symbol_risk",
            0.0,
        ),
    ],
)
def test_rejects_invalid_configuration(
    parameter,
    value,
):
    configuration = {
        "maximum_total_open_risk": 1000.0,
        "maximum_floating_loss": 600.0,
        "maximum_long_risk": 700.0,
        "maximum_short_risk": 700.0,
        "maximum_symbol_risk": 500.0,
    }

    configuration[
        parameter
    ] = value

    with pytest.raises(
        ValueError,
        match=parameter,
    ):
        PortfolioRiskEngineV2(
            **configuration,
        )


def test_rejects_sub_limits_above_total_risk():
    with pytest.raises(
        ValueError,
        match="maximum_long_risk",
    ):
        PortfolioRiskEngineV2(
            maximum_total_open_risk=500.0,
            maximum_floating_loss=300.0,
            maximum_long_risk=600.0,
            maximum_short_risk=400.0,
            maximum_symbol_risk=300.0,
        )

    with pytest.raises(
        ValueError,
        match="maximum_short_risk",
    ):
        PortfolioRiskEngineV2(
            maximum_total_open_risk=500.0,
            maximum_floating_loss=300.0,
            maximum_long_risk=400.0,
            maximum_short_risk=600.0,
            maximum_symbol_risk=300.0,
        )

    with pytest.raises(
        ValueError,
        match="maximum_symbol_risk",
    ):
        PortfolioRiskEngineV2(
            maximum_total_open_risk=500.0,
            maximum_floating_loss=300.0,
            maximum_long_risk=400.0,
            maximum_short_risk=400.0,
            maximum_symbol_risk=600.0,
        )
