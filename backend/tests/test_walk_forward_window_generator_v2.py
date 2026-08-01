import pytest

from backend.backtesting.walk_forward_window_generator_v2 import (
    WalkForwardWindowGeneratorV2,
)


def test_generates_rolling_walk_forward_windows():

    generator = WalkForwardWindowGeneratorV2(
        training_size=6,
        testing_size=2,
        step_size=2,
    )

    windows = generator.generate(
        total_items=12,
    )

    assert windows == [
        {
            "window_index": 0,
            "training_start": 0,
            "training_end": 6,
            "testing_start": 6,
            "testing_end": 8,
        },
        {
            "window_index": 1,
            "training_start": 2,
            "training_end": 8,
            "testing_start": 8,
            "testing_end": 10,
        },
        {
            "window_index": 2,
            "training_start": 4,
            "training_end": 10,
            "testing_start": 10,
            "testing_end": 12,
        },
    ]


def test_generates_single_window():

    generator = WalkForwardWindowGeneratorV2(
        training_size=5,
        testing_size=2,
        step_size=2,
    )

    windows = generator.generate(
        total_items=7,
    )

    assert windows == [
        {
            "window_index": 0,
            "training_start": 0,
            "training_end": 5,
            "testing_start": 5,
            "testing_end": 7,
        },
    ]


def test_returns_empty_when_not_enough_items():

    generator = WalkForwardWindowGeneratorV2(
        training_size=5,
        testing_size=2,
        step_size=1,
    )

    assert generator.generate(
        total_items=6,
    ) == []


@pytest.mark.parametrize(
    (
        "training_size",
        "testing_size",
        "step_size",
    ),
    [
        (0, 2, 1),
        (-1, 2, 1),
        (5, 0, 1),
        (5, -1, 1),
        (5, 2, 0),
        (5, 2, -1),
    ],
)
def test_rejects_non_positive_window_sizes(
    training_size,
    testing_size,
    step_size,
):

    with pytest.raises(
        ValueError,
    ):
        WalkForwardWindowGeneratorV2(
            training_size=training_size,
            testing_size=testing_size,
            step_size=step_size,
        )


@pytest.mark.parametrize(
    (
        "training_size",
        "testing_size",
        "step_size",
    ),
    [
        ("5", 2, 1),
        (5, "2", 1),
        (5, 2, "1"),
    ],
)
def test_rejects_non_integer_window_sizes(
    training_size,
    testing_size,
    step_size,
):

    with pytest.raises(
        TypeError,
    ):
        WalkForwardWindowGeneratorV2(
            training_size=training_size,
            testing_size=testing_size,
            step_size=step_size,
        )


@pytest.mark.parametrize(
    "total_items",
    [
        -1,
        -10,
    ],
)
def test_rejects_negative_total_items(
    total_items,
):

    generator = WalkForwardWindowGeneratorV2(
        training_size=5,
        testing_size=2,
        step_size=1,
    )

    with pytest.raises(
        ValueError,
    ):
        generator.generate(
            total_items=total_items,
        )


def test_rejects_non_integer_total_items():

    generator = WalkForwardWindowGeneratorV2(
        training_size=5,
        testing_size=2,
        step_size=1,
    )

    with pytest.raises(
        TypeError,
    ):
        generator.generate(
            total_items="10",
        )
