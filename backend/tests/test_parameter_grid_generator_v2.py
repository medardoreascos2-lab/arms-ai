import pytest

from backend.backtesting.parameter_grid_generator_v2 import (
    ParameterGridGeneratorV2,
)


def test_generates_all_combinations():

    generator = ParameterGridGeneratorV2()

    grid = generator.generate(
        {
            "ema": [20, 50],
            "stop_loss": [20, 30],
            "take_profit": [40, 80],
        }
    )

    assert len(grid) == 8

    assert {
        "ema": 20,
        "stop_loss": 20,
        "take_profit": 40,
    } in grid

    assert {
        "ema": 50,
        "stop_loss": 30,
        "take_profit": 80,
    } in grid


def test_single_parameter():

    generator = ParameterGridGeneratorV2()

    grid = generator.generate(
        {
            "ema": [20, 50, 100],
        }
    )

    assert len(grid) == 3


def test_empty_grid():

    generator = ParameterGridGeneratorV2()

    assert generator.generate({}) == []


def test_rejects_invalid_grid():

    generator = ParameterGridGeneratorV2()

    with pytest.raises(
        TypeError,
    ):
        generator.generate(
            [
                1,
                2,
            ]
        )


def test_rejects_non_iterable_values():

    generator = ParameterGridGeneratorV2()

    with pytest.raises(
        TypeError,
    ):
        generator.generate(
            {
                "ema": 20,
            }
        )
