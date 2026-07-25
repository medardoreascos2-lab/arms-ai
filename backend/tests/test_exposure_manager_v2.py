import pytest

from backend.execution.exposure_manager_v2 import (
    ExposureManagerV2,
)


def build_manager() -> ExposureManagerV2:
    return ExposureManagerV2(
        maximum_total_open_risk=500.0,
        maximum_symbol_open_risk=300.0,
        maximum_total_contracts=10,
        maximum_symbol_contracts=6,
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
            "stop_loss": 110.0,
            "point_value": 5.0,
        },
    ]


def test_calculates_current_exposure():
    manager = build_manager()

    result = manager.evaluate(
        open_positions=build_positions(),
        candidate_symbol="NQ",
        candidate_contracts=2,
        candidate_stop_points=10.0,
        candidate_point_value=2.0,
    )

    assert result["approved"] is True

    assert (
        result["current_total_open_risk"]
        == 90.0
    )

    assert (
        result["current_symbol_open_risk"]
        == 40.0
    )

    assert (
        result["current_total_contracts"]
        == 3
    )

    assert (
        result["current_symbol_contracts"]
        == 2
    )


def test_calculates_candidate_risk():
    manager = build_manager()

    result = manager.evaluate(
        open_positions=[],
        candidate_symbol="NQ",
        candidate_contracts=2,
        candidate_stop_points=20.0,
        candidate_point_value=2.0,
    )

    assert result["candidate_risk"] == 80.0
    assert result["projected_total_open_risk"] == 80.0
    assert result["projected_symbol_open_risk"] == 80.0


def test_blocks_total_open_risk():
    manager = build_manager()

    positions = [
        {
            "position_id": "position-001",
            "symbol": "ES",
            "status": "OPEN",
            "direction": "LONG",
            "quantity": 5,
            "entry_price": 100.0,
            "stop_loss": 90.0,
            "point_value": 8.0,
        },
    ]

    result = manager.evaluate(
        open_positions=positions,
        candidate_symbol="NQ",
        candidate_contracts=3,
        candidate_stop_points=20.0,
        candidate_point_value=2.0,
    )

    assert result["approved"] is False

    assert (
        "maximum_total_open_risk_exceeded"
        in result["blocking_reasons"]
    )


def test_blocks_symbol_open_risk():
    manager = build_manager()

    positions = [
        {
            "position_id": "position-001",
            "symbol": "NQ",
            "status": "OPEN",
            "direction": "LONG",
            "quantity": 5,
            "entry_price": 100.0,
            "stop_loss": 80.0,
            "point_value": 2.0,
        },
    ]

    result = manager.evaluate(
        open_positions=positions,
        candidate_symbol="NQ",
        candidate_contracts=3,
        candidate_stop_points=20.0,
        candidate_point_value=2.0,
    )

    assert result["approved"] is False

    assert (
        "maximum_symbol_open_risk_exceeded"
        in result["blocking_reasons"]
    )


def test_blocks_total_contracts():
    manager = build_manager()

    positions = [
        {
            "position_id": "position-001",
            "symbol": "ES",
            "status": "OPEN",
            "direction": "LONG",
            "quantity": 9,
            "entry_price": 100.0,
            "stop_loss": 99.0,
            "point_value": 1.0,
        },
    ]

    result = manager.evaluate(
        open_positions=positions,
        candidate_symbol="NQ",
        candidate_contracts=2,
        candidate_stop_points=5.0,
        candidate_point_value=2.0,
    )

    assert result["approved"] is False

    assert (
        "maximum_total_contracts_exceeded"
        in result["blocking_reasons"]
    )


def test_blocks_symbol_contracts():
    manager = build_manager()

    positions = [
        {
            "position_id": "position-001",
            "symbol": "NQ",
            "status": "OPEN",
            "direction": "LONG",
            "quantity": 5,
            "entry_price": 100.0,
            "stop_loss": 99.0,
            "point_value": 1.0,
        },
    ]

    result = manager.evaluate(
        open_positions=positions,
        candidate_symbol="NQ",
        candidate_contracts=2,
        candidate_stop_points=5.0,
        candidate_point_value=2.0,
    )

    assert result["approved"] is False

    assert (
        "maximum_symbol_contracts_exceeded"
        in result["blocking_reasons"]
    )


def test_ignores_closed_positions():
    manager = build_manager()

    positions = [
        {
            "position_id": "position-001",
            "symbol": "NQ",
            "status": "CLOSED",
            "direction": "LONG",
            "quantity": 100,
            "entry_price": 100.0,
            "stop_loss": 50.0,
            "point_value": 20.0,
        },
    ]

    result = manager.evaluate(
        open_positions=positions,
        candidate_symbol="NQ",
        candidate_contracts=1,
        candidate_stop_points=10.0,
        candidate_point_value=2.0,
    )

    assert result["approved"] is True
    assert result["current_total_open_risk"] == 0.0
    assert result["current_total_contracts"] == 0


def test_normalizes_candidate_symbol():
    manager = build_manager()

    result = manager.evaluate(
        open_positions=[],
        candidate_symbol=" nq ",
        candidate_contracts=1,
        candidate_stop_points=10.0,
        candidate_point_value=2.0,
    )

    assert result["candidate_symbol"] == "NQ"


def test_returns_remaining_capacity():
    manager = build_manager()

    result = manager.evaluate(
        open_positions=[],
        candidate_symbol="NQ",
        candidate_contracts=2,
        candidate_stop_points=20.0,
        candidate_point_value=2.0,
    )

    assert (
        result["remaining_total_open_risk_capacity"]
        == 420.0
    )

    assert (
        result["remaining_symbol_open_risk_capacity"]
        == 220.0
    )

    assert (
        result["remaining_total_contract_capacity"]
        == 8
    )

    assert (
        result["remaining_symbol_contract_capacity"]
        == 4
    )


def test_rejects_invalid_open_positions_type():
    manager = build_manager()

    with pytest.raises(
        TypeError,
        match="open_positions",
    ):
        manager.evaluate(
            open_positions=object(),
            candidate_symbol="NQ",
            candidate_contracts=1,
            candidate_stop_points=10.0,
            candidate_point_value=2.0,
        )


def test_rejects_invalid_position_item():
    manager = build_manager()

    with pytest.raises(
        TypeError,
        match="position",
    ):
        manager.evaluate(
            open_positions=[
                object(),
            ],
            candidate_symbol="NQ",
            candidate_contracts=1,
            candidate_stop_points=10.0,
            candidate_point_value=2.0,
        )


def test_rejects_empty_candidate_symbol():
    manager = build_manager()

    with pytest.raises(
        ValueError,
        match="candidate_symbol",
    ):
        manager.evaluate(
            open_positions=[],
            candidate_symbol=" ",
            candidate_contracts=1,
            candidate_stop_points=10.0,
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
            "candidate_stop_points",
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
    manager = build_manager()

    arguments = {
        "open_positions": [],
        "candidate_symbol": "NQ",
        "candidate_contracts": 1,
        "candidate_stop_points": 10.0,
        "candidate_point_value": 2.0,
    }

    arguments[
        parameter
    ] = value

    with pytest.raises(
        ValueError,
        match=parameter,
    ):
        manager.evaluate(
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
            "maximum_symbol_open_risk",
            0.0,
        ),
        (
            "maximum_total_contracts",
            0,
        ),
        (
            "maximum_symbol_contracts",
            0,
        ),
    ],
)
def test_rejects_invalid_configuration(
    parameter,
    value,
):
    configuration = {
        "maximum_total_open_risk": 500.0,
        "maximum_symbol_open_risk": 300.0,
        "maximum_total_contracts": 10,
        "maximum_symbol_contracts": 6,
    }

    configuration[
        parameter
    ] = value

    with pytest.raises(
        ValueError,
        match=parameter,
    ):
        ExposureManagerV2(
            **configuration,
        )


def test_rejects_symbol_limits_above_total_limits():
    with pytest.raises(
        ValueError,
        match="maximum_symbol_open_risk",
    ):
        ExposureManagerV2(
            maximum_total_open_risk=200.0,
            maximum_symbol_open_risk=300.0,
            maximum_total_contracts=10,
            maximum_symbol_contracts=6,
        )

    with pytest.raises(
        ValueError,
        match="maximum_symbol_contracts",
    ):
        ExposureManagerV2(
            maximum_total_open_risk=500.0,
            maximum_symbol_open_risk=300.0,
            maximum_total_contracts=5,
            maximum_symbol_contracts=6,
        )
