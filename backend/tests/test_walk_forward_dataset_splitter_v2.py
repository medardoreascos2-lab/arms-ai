import pytest

from backend.backtesting.walk_forward_dataset_splitter_v2 import (
    WalkForwardDatasetSplitterV2,
)
from backend.backtesting.walk_forward_window_generator_v2 import (
    WalkForwardWindowGeneratorV2,
)


def build_items():

    return [
        {
            "index": index,
            "close": 20000.0 + index,
        }
        for index in range(12)
    ]


def test_splits_dataset_using_walk_forward_windows():

    items = build_items()

    windows = WalkForwardWindowGeneratorV2(
        training_size=6,
        testing_size=2,
        step_size=2,
    ).generate(
        total_items=len(items),
    )

    splitter = WalkForwardDatasetSplitterV2()

    datasets = splitter.split(
        items=items,
        windows=windows,
    )

    assert len(datasets) == 3

    first = datasets[0]
    second = datasets[1]
    third = datasets[2]

    assert first["window_index"] == 0

    assert [
        item["index"]
        for item in first["training_items"]
    ] == [
        0,
        1,
        2,
        3,
        4,
        5,
    ]

    assert [
        item["index"]
        for item in first["testing_items"]
    ] == [
        6,
        7,
    ]

    assert [
        item["index"]
        for item in second["training_items"]
    ] == [
        2,
        3,
        4,
        5,
        6,
        7,
    ]

    assert [
        item["index"]
        for item in second["testing_items"]
    ] == [
        8,
        9,
    ]

    assert [
        item["index"]
        for item in third["training_items"]
    ] == [
        4,
        5,
        6,
        7,
        8,
        9,
    ]

    assert [
        item["index"]
        for item in third["testing_items"]
    ] == [
        10,
        11,
    ]


def test_preserves_window_boundaries():

    items = build_items()

    windows = [
        {
            "window_index": 5,
            "training_start": 1,
            "training_end": 5,
            "testing_start": 5,
            "testing_end": 7,
        },
    ]

    datasets = WalkForwardDatasetSplitterV2().split(
        items=items,
        windows=windows,
    )

    assert datasets == [
        {
            "window_index": 5,
            "training_start": 1,
            "training_end": 5,
            "testing_start": 5,
            "testing_end": 7,
            "training_items": items[1:5],
            "testing_items": items[5:7],
        },
    ]


def test_returns_empty_for_empty_windows():

    splitter = WalkForwardDatasetSplitterV2()

    assert splitter.split(
        items=build_items(),
        windows=[],
    ) == []


def test_returns_independent_collections():

    items = build_items()

    windows = [
        {
            "window_index": 0,
            "training_start": 0,
            "training_end": 4,
            "testing_start": 4,
            "testing_end": 6,
        },
    ]

    datasets = WalkForwardDatasetSplitterV2().split(
        items=items,
        windows=windows,
    )

    datasets[0]["training_items"][0]["close"] = 0.0

    assert items[0]["close"] == 20000.0


@pytest.mark.parametrize(
    "items",
    [
        None,
        10,
        "candles",
        {
            "close": 20000.0,
        },
    ],
)
def test_rejects_invalid_items(
    items,
):

    splitter = WalkForwardDatasetSplitterV2()

    with pytest.raises(
        TypeError,
        match="items",
    ):
        splitter.split(
            items=items,
            windows=[],
        )


@pytest.mark.parametrize(
    "windows",
    [
        None,
        10,
        "windows",
        {
            "window_index": 0,
        },
    ],
)
def test_rejects_invalid_windows(
    windows,
):

    splitter = WalkForwardDatasetSplitterV2()

    with pytest.raises(
        TypeError,
        match="windows",
    ):
        splitter.split(
            items=build_items(),
            windows=windows,
        )


def test_rejects_non_dict_window():

    splitter = WalkForwardDatasetSplitterV2()

    with pytest.raises(
        TypeError,
        match="window",
    ):
        splitter.split(
            items=build_items(),
            windows=[
                object(),
            ],
        )


@pytest.mark.parametrize(
    "missing_key",
    [
        "window_index",
        "training_start",
        "training_end",
        "testing_start",
        "testing_end",
    ],
)
def test_rejects_missing_window_key(
    missing_key,
):

    window = {
        "window_index": 0,
        "training_start": 0,
        "training_end": 4,
        "testing_start": 4,
        "testing_end": 6,
    }

    window.pop(
        missing_key
    )

    splitter = WalkForwardDatasetSplitterV2()

    with pytest.raises(
        ValueError,
        match=missing_key,
    ):
        splitter.split(
            items=build_items(),
            windows=[
                window,
            ],
        )


def test_rejects_invalid_boundaries():

    splitter = WalkForwardDatasetSplitterV2()

    with pytest.raises(
        ValueError,
        match="límites",
    ):
        splitter.split(
            items=build_items(),
            windows=[
                {
                    "window_index": 0,
                    "training_start": 0,
                    "training_end": 8,
                    "testing_start": 7,
                    "testing_end": 10,
                },
            ],
        )


def test_rejects_out_of_range_boundaries():

    splitter = WalkForwardDatasetSplitterV2()

    with pytest.raises(
        ValueError,
        match="rango",
    ):
        splitter.split(
            items=build_items(),
            windows=[
                {
                    "window_index": 0,
                    "training_start": 0,
                    "training_end": 10,
                    "testing_start": 10,
                    "testing_end": 20,
                },
            ],
        )
