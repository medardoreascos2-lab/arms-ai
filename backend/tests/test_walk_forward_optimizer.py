from dataclasses import dataclass

import pytest

from backend.backtesting.parameter_evaluator import (
    ParameterEvaluation,
)
from backend.backtesting.walk_forward_optimizer import (
    WalkForwardOptimizationResult,
    WalkForwardOptimizer,
)


@dataclass
class DummyGrid:
    combinations: list[dict]

    def generate(self):
        return [
            dict(parameters)
            for parameters in self.combinations
        ]


class DummyEvaluator:
    def __init__(
        self,
        training_scores,
        testing_scores,
        training_candles,
        testing_candles,
    ):
        self.training_scores = training_scores
        self.testing_scores = testing_scores
        self.training_candles = training_candles
        self.testing_candles = testing_candles
        self.calls = []

    def evaluate(
        self,
        parameters,
        candles,
    ):
        parameters_copy = dict(parameters)
        self.calls.append(
            (
                parameters_copy,
                candles,
            )
        )

        key = parameters_copy["name"]

        if candles is self.training_candles:
            net_profit = self.training_scores[key]
        elif candles is self.testing_candles:
            net_profit = self.testing_scores[key]
        else:
            raise AssertionError(
                "Se recibió una lista de velas inesperada."
            )

        return ParameterEvaluation(
            parameters=parameters_copy,
            net_profit=net_profit,
            profit_factor=1.5,
            max_drawdown=5.0,
            win_rate=60.0,
            result={
                "parameters": parameters_copy,
                "net_profit": net_profit,
            },
        )


class DummySelector:
    def __init__(self):
        self.received_candidates = None

    def select(self, candidates):
        self.received_candidates = candidates

        return max(
            candidates,
            key=lambda candidate: candidate.net_profit,
        )


def test_optimizer_selects_best_training_parameters():
    training_candles = [1, 2, 3]
    testing_candles = [4, 5]

    evaluator = DummyEvaluator(
        training_scores={
            "A": 10.0,
            "B": 25.0,
            "C": -5.0,
        },
        testing_scores={
            "A": 8.0,
            "B": 12.0,
            "C": -3.0,
        },
        training_candles=training_candles,
        testing_candles=testing_candles,
    )

    selector = DummySelector()

    optimizer = WalkForwardOptimizer(
        parameter_grid=DummyGrid(
            [
                {"name": "A"},
                {"name": "B"},
                {"name": "C"},
            ]
        ),
        evaluator=evaluator,
        selector=selector,
    )

    result = optimizer.optimize(
        training_candles=training_candles,
        testing_candles=testing_candles,
    )

    assert isinstance(
        result,
        WalkForwardOptimizationResult,
    )

    assert result.selected_parameters == {
        "name": "B",
    }

    assert result.training_evaluation.net_profit == 25.0
    assert result.testing_evaluation.net_profit == 12.0

    assert len(result.training_evaluations) == 3
    assert selector.received_candidates == (
        result.training_evaluations
    )


def test_optimizer_evaluates_selected_parameters_on_testing_data():
    training_candles = [1]
    testing_candles = [2]

    evaluator = DummyEvaluator(
        training_scores={
            "A": 5.0,
            "B": 15.0,
        },
        testing_scores={
            "A": 100.0,
            "B": -2.0,
        },
        training_candles=training_candles,
        testing_candles=testing_candles,
    )

    result = WalkForwardOptimizer(
        parameter_grid=DummyGrid(
            [
                {"name": "A"},
                {"name": "B"},
            ]
        ),
        evaluator=evaluator,
        selector=DummySelector(),
    ).optimize(
        training_candles=training_candles,
        testing_candles=testing_candles,
    )

    assert result.selected_parameters == {
        "name": "B",
    }

    assert result.testing_evaluation.net_profit == -2.0

    assert evaluator.calls[-1] == (
        {"name": "B"},
        testing_candles,
    )


def test_optimizer_preserves_parameter_copy():
    parameters = {
        "name": "A",
    }

    training_candles = [1]
    testing_candles = [2]

    result = WalkForwardOptimizer(
        parameter_grid=DummyGrid(
            [parameters]
        ),
        evaluator=DummyEvaluator(
            training_scores={"A": 10.0},
            testing_scores={"A": 5.0},
            training_candles=training_candles,
            testing_candles=testing_candles,
        ),
        selector=DummySelector(),
    ).optimize(
        training_candles=training_candles,
        testing_candles=testing_candles,
    )

    parameters["name"] = "CHANGED"

    assert result.selected_parameters == {
        "name": "A",
    }


def test_optimizer_rejects_empty_training_candles():
    optimizer = WalkForwardOptimizer(
        parameter_grid=DummyGrid(
            [{"name": "A"}]
        ),
        evaluator=object(),
        selector=object(),
    )

    with pytest.raises(
        ValueError,
        match="training_candles",
    ):
        optimizer.optimize(
            training_candles=[],
            testing_candles=[1],
        )


def test_optimizer_rejects_empty_testing_candles():
    optimizer = WalkForwardOptimizer(
        parameter_grid=DummyGrid(
            [{"name": "A"}]
        ),
        evaluator=object(),
        selector=object(),
    )

    with pytest.raises(
        ValueError,
        match="testing_candles",
    ):
        optimizer.optimize(
            training_candles=[1],
            testing_candles=[],
        )


def test_optimizer_rejects_empty_parameter_grid():
    optimizer = WalkForwardOptimizer(
        parameter_grid=DummyGrid([]),
        evaluator=object(),
        selector=object(),
    )

    with pytest.raises(
        ValueError,
        match="combinaciones",
    ):
        optimizer.optimize(
            training_candles=[1],
            testing_candles=[2],
        )


@pytest.mark.parametrize(
    ("argument_name", "parameter_grid", "evaluator", "selector"),
    [
        (
            "parameter_grid",
            None,
            object(),
            object(),
        ),
        (
            "evaluator",
            DummyGrid([{"name": "A"}]),
            None,
            object(),
        ),
        (
            "selector",
            DummyGrid([{"name": "A"}]),
            object(),
            None,
        ),
    ],
)
def test_optimizer_requires_dependencies(
    argument_name,
    parameter_grid,
    evaluator,
    selector,
):
    with pytest.raises(
        TypeError,
        match=argument_name,
    ):
        WalkForwardOptimizer(
            parameter_grid=parameter_grid,
            evaluator=evaluator,
            selector=selector,
        )
