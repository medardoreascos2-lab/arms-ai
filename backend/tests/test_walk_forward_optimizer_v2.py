from pathlib import Path

import pytest

from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)
from backend.backtesting.walk_forward_optimizer_v2 import (
    WalkForwardOptimizerV2,
)


class FakeTrainingOptimizerV2:

    def __init__(self) -> None:
        self.calls = []

    def optimize(
        self,
        *,
        candidates,
        output_directory,
    ):
        self.calls.append(
            {
                "candidates": candidates,
                "output_directory": Path(
                    output_directory
                ),
            }
        )

        window_index = int(
            Path(output_directory).name.split("_")[-1]
        )

        if window_index == 0:
            best = {
                "name": "EMA50",
                "score": 90.0,
                "parameters": {
                    "ema": 50,
                },
            }
        else:
            best = {
                "name": "EMA20",
                "score": 82.0,
                "parameters": {
                    "ema": 20,
                },
            }

        class Result:

            def best_strategy(self):
                return dict(best)

        return Result()


class FakeCandidateFactoryV2:

    def __init__(self) -> None:
        self.calls = []

    def build(
        self,
        *,
        parameter_sets,
    ):
        normalized = list(
            parameter_sets
        )

        self.calls.append(
            normalized
        )

        return [
            {
                "parameters": dict(
                    parameters
                ),
            }
            for parameters in normalized
        ]


class FakeTestingEvaluatorV2:

    def __init__(self) -> None:
        self.calls = []

    def evaluate(
        self,
        *,
        testing_items,
        parameters,
        output_directory,
    ):
        self.calls.append(
            {
                "testing_items": list(
                    testing_items
                ),
                "parameters": dict(
                    parameters
                ),
                "output_directory": Path(
                    output_directory
                ),
            }
        )

        ema = parameters["ema"]

        if ema == 50:
            return {
                "score": 84.0,
                "net_pnl": 300.0,
                "win_rate": 0.60,
                "maximum_drawdown": 120.0,
            }

        return {
            "score": 70.0,
            "net_pnl": 100.0,
            "win_rate": 0.50,
            "maximum_drawdown": 220.0,
        }


def build_datasets():

    return [
        {
            "window_index": 0,
            "training_start": 0,
            "training_end": 4,
            "testing_start": 4,
            "testing_end": 6,
            "training_items": [
                0,
                1,
                2,
                3,
            ],
            "testing_items": [
                4,
                5,
            ],
        },
        {
            "window_index": 1,
            "training_start": 2,
            "training_end": 6,
            "testing_start": 6,
            "testing_end": 8,
            "training_items": [
                2,
                3,
                4,
                5,
            ],
            "testing_items": [
                6,
                7,
            ],
        },
    ]


def test_executes_walk_forward_optimization(
    tmp_path,
):

    training_optimizer = (
        FakeTrainingOptimizerV2()
    )

    candidate_factory = (
        FakeCandidateFactoryV2()
    )

    testing_evaluator = (
        FakeTestingEvaluatorV2()
    )

    optimizer = WalkForwardOptimizerV2(
        training_optimizer=training_optimizer,
        candidate_factory=candidate_factory,
        testing_evaluator=testing_evaluator,
        continue_on_error=False,
    )

    result = optimizer.optimize(
        datasets=build_datasets(),
        parameter_sets=[
            {
                "ema": 20,
            },
            {
                "ema": 50,
            },
        ],
        output_directory=tmp_path,
    )

    assert isinstance(
        result,
        WalkForwardOptimizationResultV2,
    )

    assert result.total_windows == 2
    assert result.successful_windows == 2
    assert result.failed_windows == 0

    assert result.window_results[0] == {
        "window_index": 0,
        "success": True,
        "training_start": 0,
        "training_end": 4,
        "testing_start": 4,
        "testing_end": 6,
        "training_score": 90.0,
        "testing_score": 84.0,
        "testing_net_pnl": 300.0,
        "testing_win_rate": 0.60,
        "testing_maximum_drawdown": 120.0,
        "best_parameters": {
            "ema": 50,
        },
        "best_training_strategy": {
            "name": "EMA50",
            "score": 90.0,
            "parameters": {
                "ema": 50,
            },
        },
    }

    assert result.window_results[1][
        "best_parameters"
    ] == {
        "ema": 20,
    }

    assert (
        result.average_testing_score
        == 77.0
    )

    assert len(
        training_optimizer.calls
    ) == 2

    assert len(
        testing_evaluator.calls
    ) == 2


def test_continues_when_window_fails(
    tmp_path,
):

    class FailingEvaluator:

        def __init__(self):
            self.calls = 0

        def evaluate(
            self,
            *,
            testing_items,
            parameters,
            output_directory,
        ):
            self.calls += 1

            if self.calls == 2:
                raise RuntimeError(
                    "testing failed"
                )

            return {
                "score": 80.0,
                "net_pnl": 100.0,
                "win_rate": 0.55,
                "maximum_drawdown": 100.0,
            }

    optimizer = WalkForwardOptimizerV2(
        training_optimizer=(
            FakeTrainingOptimizerV2()
        ),
        candidate_factory=(
            FakeCandidateFactoryV2()
        ),
        testing_evaluator=(
            FailingEvaluator()
        ),
        continue_on_error=True,
    )

    result = optimizer.optimize(
        datasets=build_datasets(),
        parameter_sets=[
            {
                "ema": 20,
            },
            {
                "ema": 50,
            },
        ],
        output_directory=tmp_path,
    )

    assert result.total_windows == 2
    assert result.successful_windows == 1
    assert result.failed_windows == 1

    failed = result.window_results[1]

    assert failed["success"] is False
    assert failed["error"] == {
        "type": "RuntimeError",
        "message": "testing failed",
    }


def test_stops_when_window_fails(
    tmp_path,
):

    class FailingEvaluator:

        def evaluate(
            self,
            *,
            testing_items,
            parameters,
            output_directory,
        ):
            raise RuntimeError(
                "testing failed"
            )

    optimizer = WalkForwardOptimizerV2(
        training_optimizer=(
            FakeTrainingOptimizerV2()
        ),
        candidate_factory=(
            FakeCandidateFactoryV2()
        ),
        testing_evaluator=(
            FailingEvaluator()
        ),
        continue_on_error=False,
    )

    with pytest.raises(
        RuntimeError,
        match="testing failed",
    ):
        optimizer.optimize(
            datasets=build_datasets(),
            parameter_sets=[
                {
                    "ema": 20,
                },
            ],
            output_directory=tmp_path,
        )


@pytest.mark.parametrize(
    "datasets",
    [
        None,
        10,
        "datasets",
        {},
    ],
)
def test_rejects_invalid_datasets(
    datasets,
    tmp_path,
):

    optimizer = WalkForwardOptimizerV2(
        training_optimizer=(
            FakeTrainingOptimizerV2()
        ),
        candidate_factory=(
            FakeCandidateFactoryV2()
        ),
        testing_evaluator=(
            FakeTestingEvaluatorV2()
        ),
    )

    with pytest.raises(
        TypeError,
        match="datasets",
    ):
        optimizer.optimize(
            datasets=datasets,
            parameter_sets=[],
            output_directory=tmp_path,
        )


def test_rejects_empty_parameter_sets(
    tmp_path,
):

    optimizer = WalkForwardOptimizerV2(
        training_optimizer=(
            FakeTrainingOptimizerV2()
        ),
        candidate_factory=(
            FakeCandidateFactoryV2()
        ),
        testing_evaluator=(
            FakeTestingEvaluatorV2()
        ),
    )

    with pytest.raises(
        ValueError,
        match="parameter_sets",
    ):
        optimizer.optimize(
            datasets=build_datasets(),
            parameter_sets=[],
            output_directory=tmp_path,
        )


def test_rejects_invalid_dependencies():

    with pytest.raises(
        TypeError,
        match="optimize",
    ):
        WalkForwardOptimizerV2(
            training_optimizer=object(),
            candidate_factory=(
                FakeCandidateFactoryV2()
            ),
            testing_evaluator=(
                FakeTestingEvaluatorV2()
            ),
        )

    with pytest.raises(
        TypeError,
        match="build",
    ):
        WalkForwardOptimizerV2(
            training_optimizer=(
                FakeTrainingOptimizerV2()
            ),
            candidate_factory=object(),
            testing_evaluator=(
                FakeTestingEvaluatorV2()
            ),
        )

    with pytest.raises(
        TypeError,
        match="evaluate",
    ):
        WalkForwardOptimizerV2(
            training_optimizer=(
                FakeTrainingOptimizerV2()
            ),
            candidate_factory=(
                FakeCandidateFactoryV2()
            ),
            testing_evaluator=object(),
        )
