from dataclasses import dataclass

import pytest

from backend.backtesting.walk_forward_optimization_report import (
    WalkForwardOptimizationReport,
)
from backend.backtesting.walk_forward_optimization_runner import (
    WalkForwardOptimizationRunner,
)
from backend.backtesting.walk_forward_splitter import (
    WalkForwardSplitter,
)


@dataclass
class DummyOptimizationResult:
    selected_parameters: dict
    training_evaluation: object
    testing_evaluation: object
    training_evaluations: list


class DummyOptimizer:
    def __init__(self):
        self.calls = []

    def optimize(
        self,
        training_candles,
        testing_candles,
    ):
        self.calls.append(
            (
                training_candles,
                testing_candles,
            )
        )

        return DummyOptimizationResult(
            selected_parameters={
                "window": len(self.calls),
            },
            training_evaluation=object(),
            testing_evaluation=object(),
            training_evaluations=[],
        )


class DummyReportFactory:
    def __init__(self, report):
        self.report = report
        self.received_results = None

    def __call__(self, results):
        self.received_results = results
        return self.report


def build_empty_report():
    return WalkForwardOptimizationReport(
        total_windows=0,
        profitable_testing_windows=0,
        losing_testing_windows=0,
        breakeven_testing_windows=0,
        total_training_net_profit=0.0,
        total_testing_net_profit=0.0,
        average_training_net_profit=0.0,
        average_testing_net_profit=0.0,
        average_performance_degradation=0.0,
        testing_profitable_rate=0.0,
        overfit_windows=0,
        overfit_rate=0.0,
        windows=[],
    )


def test_runner_optimizes_all_windows():
    candles = list(range(180))

    splitter = WalkForwardSplitter(
        training_size=100,
        testing_size=20,
        step_size=20,
    )

    optimizer = DummyOptimizer()
    expected_report = build_empty_report()

    report_factory = DummyReportFactory(
        expected_report
    )

    runner = WalkForwardOptimizationRunner(
        splitter=splitter,
        optimizer=optimizer,
        report_factory=report_factory,
    )

    report = runner.run(
        candles=candles,
    )

    assert report is expected_report
    assert len(optimizer.calls) == 4
    assert len(report_factory.received_results) == 4

    assert optimizer.calls[0] == (
        candles[0:100],
        candles[100:120],
    )

    assert optimizer.calls[-1] == (
        candles[60:160],
        candles[160:180],
    )


def test_runner_uses_default_report_factory():
    class Evaluation:
        net_profit = 0.0

    class Optimizer:
        def optimize(
            self,
            training_candles,
            testing_candles,
        ):
            return DummyOptimizationResult(
                selected_parameters={},
                training_evaluation=Evaluation(),
                testing_evaluation=Evaluation(),
                training_evaluations=[],
            )

    runner = WalkForwardOptimizationRunner(
        splitter=WalkForwardSplitter(
            training_size=2,
            testing_size=1,
            step_size=1,
        ),
        optimizer=Optimizer(),
    )

    report = runner.run(
        candles=[1, 2, 3],
    )

    assert isinstance(
        report,
        WalkForwardOptimizationReport,
    )
    assert report.total_windows == 1


def test_runner_returns_empty_report_when_data_is_insufficient():
    runner = WalkForwardOptimizationRunner(
        splitter=WalkForwardSplitter(
            training_size=100,
            testing_size=20,
            step_size=20,
        ),
        optimizer=DummyOptimizer(),
    )

    report = runner.run(
        candles=list(range(50)),
    )

    assert report.total_windows == 0
    assert report.windows == []


def test_runner_rejects_empty_candles():
    runner = WalkForwardOptimizationRunner(
        splitter=WalkForwardSplitter(
            training_size=100,
            testing_size=20,
            step_size=20,
        ),
        optimizer=DummyOptimizer(),
    )

    with pytest.raises(
        ValueError,
        match="candles",
    ):
        runner.run(
            candles=[],
        )


@pytest.mark.parametrize(
    (
        "argument_name",
        "splitter",
        "optimizer",
    ),
    [
        (
            "splitter",
            None,
            DummyOptimizer(),
        ),
        (
            "optimizer",
            WalkForwardSplitter(
                training_size=2,
                testing_size=1,
                step_size=1,
            ),
            None,
        ),
    ],
)
def test_runner_requires_dependencies(
    argument_name,
    splitter,
    optimizer,
):
    with pytest.raises(
        TypeError,
        match=argument_name,
    ):
        WalkForwardOptimizationRunner(
            splitter=splitter,
            optimizer=optimizer,
        )
