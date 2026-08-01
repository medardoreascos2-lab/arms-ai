from pathlib import Path

import pytest

from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)
from backend.backtesting.walk_forward_pipeline_v2 import (
    WalkForwardPipelineV2,
)


class FakeWindowGeneratorV2:

    def __init__(self) -> None:
        self.calls = []

    def generate(
        self,
        *,
        total_items,
    ):
        self.calls.append(
            total_items
        )

        return [
            {
                "window_index": 0,
                "training_start": 0,
                "training_end": 4,
                "testing_start": 4,
                "testing_end": 6,
            },
            {
                "window_index": 1,
                "training_start": 2,
                "training_end": 6,
                "testing_start": 6,
                "testing_end": 8,
            },
        ]


class FakeDatasetSplitterV2:

    def __init__(self) -> None:
        self.calls = []

    def split(
        self,
        *,
        items,
        windows,
    ):
        normalized_items = list(
            items
        )

        normalized_windows = list(
            windows
        )

        self.calls.append(
            {
                "items": normalized_items,
                "windows": normalized_windows,
            }
        )

        return [
            {
                **window,
                "training_items": normalized_items[
                    window["training_start"]:
                    window["training_end"]
                ],
                "testing_items": normalized_items[
                    window["testing_start"]:
                    window["testing_end"]
                ],
            }
            for window in normalized_windows
        ]


class FakeWalkForwardOptimizerV2:

    def __init__(self) -> None:
        self.calls = []

    def optimize(
        self,
        *,
        datasets,
        parameter_sets,
        output_directory,
    ) -> WalkForwardOptimizationResultV2:

        normalized_datasets = list(
            datasets
        )

        normalized_parameter_sets = list(
            parameter_sets
        )

        self.calls.append(
            {
                "datasets": normalized_datasets,
                "parameter_sets": normalized_parameter_sets,
                "output_directory": Path(
                    output_directory
                ),
            }
        )

        return WalkForwardOptimizationResultV2(
            window_results=[
                {
                    "window_index": 0,
                    "success": True,
                    "training_score": 90.0,
                    "testing_score": 82.0,
                    "testing_net_pnl": 200.0,
                    "testing_win_rate": 0.60,
                    "testing_maximum_drawdown": 100.0,
                    "best_parameters": {
                        "ema": 50,
                    },
                },
                {
                    "window_index": 1,
                    "success": True,
                    "training_score": 85.0,
                    "testing_score": 78.0,
                    "testing_net_pnl": 150.0,
                    "testing_win_rate": 0.55,
                    "testing_maximum_drawdown": 120.0,
                    "best_parameters": {
                        "ema": 20,
                    },
                },
            ],
        )


def build_items():

    return [
        {
            "index": index,
            "close": 20000.0 + index,
        }
        for index in range(8)
    ]


def build_pipeline():

    window_generator = (
        FakeWindowGeneratorV2()
    )

    dataset_splitter = (
        FakeDatasetSplitterV2()
    )

    walk_forward_optimizer = (
        FakeWalkForwardOptimizerV2()
    )

    pipeline = WalkForwardPipelineV2(
        window_generator=window_generator,
        dataset_splitter=dataset_splitter,
        walk_forward_optimizer=(
            walk_forward_optimizer
        ),
    )

    return (
        pipeline,
        window_generator,
        dataset_splitter,
        walk_forward_optimizer,
    )


def test_runs_complete_walk_forward_pipeline(
    tmp_path,
):

    (
        pipeline,
        window_generator,
        dataset_splitter,
        walk_forward_optimizer,
    ) = build_pipeline()

    items = build_items()

    parameter_sets = [
        {
            "ema": 20,
        },
        {
            "ema": 50,
        },
    ]

    result = pipeline.run(
        items=items,
        parameter_sets=parameter_sets,
        output_directory=tmp_path,
    )

    assert isinstance(
        result,
        WalkForwardOptimizationResultV2,
    )

    assert result.total_windows == 2
    assert result.successful_windows == 2
    assert result.failed_windows == 0

    assert result.average_testing_score == 80.0

    assert window_generator.calls == [
        8,
    ]

    assert len(
        dataset_splitter.calls
    ) == 1

    assert (
        dataset_splitter.calls[0]["items"]
        == items
    )

    assert len(
        dataset_splitter.calls[0]["windows"]
    ) == 2

    assert len(
        walk_forward_optimizer.calls
    ) == 1

    optimizer_call = (
        walk_forward_optimizer.calls[0]
    )

    assert len(
        optimizer_call["datasets"]
    ) == 2

    assert (
        optimizer_call["parameter_sets"]
        == parameter_sets
    )

    assert (
        optimizer_call["output_directory"]
        == tmp_path
    )


def test_returns_empty_result_when_no_windows(
    tmp_path,
):

    class EmptyWindowGenerator:

        def generate(
            self,
            *,
            total_items,
        ):
            return []

    pipeline = WalkForwardPipelineV2(
        window_generator=(
            EmptyWindowGenerator()
        ),
        dataset_splitter=(
            FakeDatasetSplitterV2()
        ),
        walk_forward_optimizer=(
            FakeWalkForwardOptimizerV2()
        ),
    )

    result = pipeline.run(
        items=[
            1,
            2,
        ],
        parameter_sets=[
            {
                "ema": 20,
            },
        ],
        output_directory=tmp_path,
    )

    assert isinstance(
        result,
        WalkForwardOptimizationResultV2,
    )

    assert result.total_windows == 0
    assert result.window_results == []


@pytest.mark.parametrize(
    "items",
    [
        None,
        10,
        "items",
        {},
    ],
)
def test_rejects_invalid_items(
    items,
    tmp_path,
):

    pipeline, _, _, _ = build_pipeline()

    with pytest.raises(
        TypeError,
        match="items",
    ):
        pipeline.run(
            items=items,
            parameter_sets=[
                {
                    "ema": 20,
                },
            ],
            output_directory=tmp_path,
        )


def test_rejects_empty_parameter_sets(
    tmp_path,
):

    pipeline, _, _, _ = build_pipeline()

    with pytest.raises(
        ValueError,
        match="parameter_sets",
    ):
        pipeline.run(
            items=build_items(),
            parameter_sets=[],
            output_directory=tmp_path,
        )


def test_rejects_invalid_dependencies():

    with pytest.raises(
        TypeError,
        match="generate",
    ):
        WalkForwardPipelineV2(
            window_generator=object(),
            dataset_splitter=(
                FakeDatasetSplitterV2()
            ),
            walk_forward_optimizer=(
                FakeWalkForwardOptimizerV2()
            ),
        )

    with pytest.raises(
        TypeError,
        match="split",
    ):
        WalkForwardPipelineV2(
            window_generator=(
                FakeWindowGeneratorV2()
            ),
            dataset_splitter=object(),
            walk_forward_optimizer=(
                FakeWalkForwardOptimizerV2()
            ),
        )

    with pytest.raises(
        TypeError,
        match="optimize",
    ):
        WalkForwardPipelineV2(
            window_generator=(
                FakeWindowGeneratorV2()
            ),
            dataset_splitter=(
                FakeDatasetSplitterV2()
            ),
            walk_forward_optimizer=object(),
        )
