import pytest

from backend.backtesting.walk_forward_splitter import (
    WalkForwardSplitter,
)


def test_walk_forward_splitter_builds_expected_windows():
    splitter = WalkForwardSplitter(
        training_size=100,
        testing_size=20,
        step_size=20,
    )

    windows = splitter.split(total_items=180)

    assert len(windows) == 4

    assert windows[0].training_start == 0
    assert windows[0].training_end == 100
    assert windows[0].testing_start == 100
    assert windows[0].testing_end == 120

    assert windows[1].training_start == 20
    assert windows[1].training_end == 120
    assert windows[1].testing_start == 120
    assert windows[1].testing_end == 140

    assert windows[-1].training_start == 60
    assert windows[-1].training_end == 160
    assert windows[-1].testing_start == 160
    assert windows[-1].testing_end == 180


def test_walk_forward_splitter_uses_rolling_windows():
    splitter = WalkForwardSplitter(
        training_size=50,
        testing_size=10,
        step_size=10,
    )

    windows = splitter.split(total_items=80)

    assert [
        (
            window.training_start,
            window.training_end,
            window.testing_start,
            window.testing_end,
        )
        for window in windows
    ] == [
        (0, 50, 50, 60),
        (10, 60, 60, 70),
        (20, 70, 70, 80),
    ]


def test_walk_forward_splitter_returns_empty_when_data_is_insufficient():
    splitter = WalkForwardSplitter(
        training_size=100,
        testing_size=20,
        step_size=20,
    )

    assert splitter.split(total_items=119) == []


@pytest.mark.parametrize(
    ("training_size", "testing_size", "step_size"),
    [
        (0, 20, 20),
        (100, 0, 20),
        (100, 20, 0),
        (-1, 20, 20),
    ],
)
def test_walk_forward_splitter_rejects_invalid_sizes(
    training_size,
    testing_size,
    step_size,
):
    with pytest.raises(
        ValueError,
        match="mayor que cero",
    ):
        WalkForwardSplitter(
            training_size=training_size,
            testing_size=testing_size,
            step_size=step_size,
        )


def test_walk_forward_splitter_rejects_invalid_total_items():
    splitter = WalkForwardSplitter(
        training_size=100,
        testing_size=20,
        step_size=20,
    )

    with pytest.raises(
        ValueError,
        match="total_items",
    ):
        splitter.split(total_items=-1)
