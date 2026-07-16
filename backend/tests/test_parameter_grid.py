import pytest

from backend.backtesting.parameter_grid import (
    ParameterGrid,
)


def test_parameter_grid_generates_all_combinations():
    grid = ParameterGrid(
        {
            "ema_period": [20, 50],
            "rsi_period": [14, 21],
            "atr_period": [14, 20],
        }
    )

    combinations = grid.generate()

    assert len(combinations) == 8

    assert combinations[0] == {
        "ema_period": 20,
        "rsi_period": 14,
        "atr_period": 14,
    }

    assert combinations[-1] == {
        "ema_period": 50,
        "rsi_period": 21,
        "atr_period": 20,
    }


def test_parameter_grid_preserves_parameter_order():
    grid = ParameterGrid(
        {
            "risk_percent": [0.25, 0.5],
            "reward_risk_ratio": [2.0, 3.0],
        }
    )

    combinations = grid.generate()

    assert combinations == [
        {
            "risk_percent": 0.25,
            "reward_risk_ratio": 2.0,
        },
        {
            "risk_percent": 0.25,
            "reward_risk_ratio": 3.0,
        },
        {
            "risk_percent": 0.5,
            "reward_risk_ratio": 2.0,
        },
        {
            "risk_percent": 0.5,
            "reward_risk_ratio": 3.0,
        },
    ]


def test_parameter_grid_supports_single_parameter():
    grid = ParameterGrid(
        {
            "ema_period": [20, 50, 100],
        }
    )

    assert grid.generate() == [
        {"ema_period": 20},
        {"ema_period": 50},
        {"ema_period": 100},
    ]


def test_parameter_grid_returns_one_empty_combination_for_empty_grid():
    grid = ParameterGrid({})

    assert grid.generate() == [{}]


def test_parameter_grid_rejects_empty_parameter_name():
    with pytest.raises(
        ValueError,
        match="nombre",
    ):
        ParameterGrid(
            {
                "": [1, 2],
            }
        )


def test_parameter_grid_rejects_empty_values():
    with pytest.raises(
        ValueError,
        match="valores",
    ):
        ParameterGrid(
            {
                "ema_period": [],
            }
        )


def test_parameter_grid_rejects_non_mapping_input():
    with pytest.raises(
        TypeError,
        match="parameters",
    ):
        ParameterGrid(
            [
                ("ema_period", [20, 50]),
            ]
        )


def test_parameter_grid_does_not_mutate_source_values():
    source = {
        "ema_period": [20, 50],
    }

    grid = ParameterGrid(source)

    source["ema_period"].append(100)

    assert grid.generate() == [
        {"ema_period": 20},
        {"ema_period": 50},
    ]
