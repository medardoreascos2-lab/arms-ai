from dataclasses import dataclass

import pytest

from backend.backtesting.parameter_evaluator import (
    ParameterEvaluation,
    ParameterEvaluator,
)


@dataclass
class DummyStatistics:
    net_profit: float
    profit_factor: float | None
    max_drawdown: float
    win_rate: float


@dataclass
class DummyBacktestResult:
    statistics: DummyStatistics


class DummyEngine:
    def __init__(
        self,
        expected_candles,
        result,
    ):
        self.expected_candles = expected_candles
        self.result = result
        self.calls = 0
        self.single_pass_calls = 0

    def run(self, candles):
        assert candles == self.expected_candles
        self.calls += 1
        return self.result

    def run_single_pass(self, candles):
        assert candles == self.expected_candles
        self.single_pass_calls += 1
        return self.result


def test_parameter_evaluator_returns_standardized_metrics():
    candles = [1, 2, 3]

    result = DummyBacktestResult(
        statistics=DummyStatistics(
            net_profit=25.0,
            profit_factor=2.5,
            max_drawdown=5.0,
            win_rate=60.0,
        )
    )

    engine = DummyEngine(
        expected_candles=candles,
        result=result,
    )

    evaluator = ParameterEvaluator(
        engine_factory=lambda parameters: engine,
    )

    evaluation = evaluator.evaluate(
        parameters={
            "ema_period": 50,
            "rsi_period": 14,
        },
        candles=candles,
    )

    assert isinstance(
        evaluation,
        ParameterEvaluation,
    )

    assert evaluation.parameters == {
        "ema_period": 50,
        "rsi_period": 14,
    }

    assert evaluation.net_profit == 25.0
    assert evaluation.profit_factor == 2.5
    assert evaluation.max_drawdown == 5.0
    assert evaluation.win_rate == 60.0
    assert evaluation.result is result
    assert engine.single_pass_calls == 1
    assert engine.calls == 0


def test_parameter_evaluator_preserves_parameters_copy():
    parameters = {
        "ema_period": 20,
    }

    evaluator = ParameterEvaluator(
        engine_factory=lambda parameters: DummyEngine(
            expected_candles=[1],
            result=DummyBacktestResult(
                statistics=DummyStatistics(
                    net_profit=1.0,
                    profit_factor=1.0,
                    max_drawdown=0.0,
                    win_rate=100.0,
                )
            ),
        ),
    )

    evaluation = evaluator.evaluate(
        parameters=parameters,
        candles=[1],
    )

    parameters["ema_period"] = 200

    assert evaluation.parameters == {
        "ema_period": 20,
    }


def test_parameter_evaluator_handles_missing_profit_factor():
    evaluator = ParameterEvaluator(
        engine_factory=lambda parameters: DummyEngine(
            expected_candles=[1],
            result=DummyBacktestResult(
                statistics=DummyStatistics(
                    net_profit=-5.0,
                    profit_factor=None,
                    max_drawdown=8.0,
                    win_rate=30.0,
                )
            ),
        ),
    )

    evaluation = evaluator.evaluate(
        parameters={},
        candles=[1],
    )

    assert evaluation.profit_factor is None


def test_parameter_evaluator_rejects_empty_candles():
    evaluator = ParameterEvaluator(
        engine_factory=lambda parameters: object(),
    )

    with pytest.raises(
        ValueError,
        match="candles",
    ):
        evaluator.evaluate(
            parameters={},
            candles=[],
        )


def test_parameter_evaluator_requires_callable_factory():
    with pytest.raises(
        TypeError,
        match="engine_factory",
    ):
        ParameterEvaluator(
            engine_factory=None,
        )


def test_parameter_evaluator_requires_statistics():
    class ResultWithoutStatistics:
        pass

    evaluator = ParameterEvaluator(
        engine_factory=lambda parameters: DummyEngine(
            expected_candles=[1],
            result=ResultWithoutStatistics(),
        ),
    )

    with pytest.raises(
        ValueError,
        match="statistics",
    ):
        evaluator.evaluate(
            parameters={},
            candles=[1],
        )


def test_parameter_evaluator_fails_closed_without_single_pass():

    class LegacyOnlyEngine:

        def run(
            self,
            candles,
        ):
            raise AssertionError(
                "legacy run() must not be used"
            )

    evaluator = ParameterEvaluator(
        engine_factory=lambda parameters: (
            LegacyOnlyEngine()
        ),
    )

    with pytest.raises(
        TypeError,
        match="run_single_pass",
    ):
        evaluator.evaluate(
            parameters={},
            candles=[1],
        )


def test_parameter_evaluator_propagates_oos_warmup_boundary():

    class WarmupAwareEngine:

        minimum_candles = 5

        def __init__(self):
            self.calls = []

        def run_single_pass(
            self,
            candles,
            *,
            minimum_candles=None,
        ):
            self.calls.append(
                {
                    "candles": list(candles),
                    "minimum_candles":
                        minimum_candles,
                }
            )

            return DummyBacktestResult(
                statistics=DummyStatistics(
                    net_profit=25.0,
                    profit_factor=2.5,
                    max_drawdown=5.0,
                    win_rate=60.0,
                )
            )

    candles = list(
        range(20)
    )

    engine = WarmupAwareEngine()

    evaluator = ParameterEvaluator(
        engine_factory=lambda parameters: engine,
    )

    evaluator.evaluate(
        parameters={
            "ema_period": 50,
        },
        candles=candles,
        warmup_count=10,
    )

    assert engine.calls == [
        {
            "candles": candles,
            "minimum_candles": 11,
        }
    ]


def test_parameter_evaluator_rejects_warmup_without_oos_data():

    evaluator = ParameterEvaluator(
        engine_factory=lambda parameters: None,
    )

    with pytest.raises(
        ValueError,
        match="warmup_count",
    ):
        evaluator.evaluate(
            parameters={},
            candles=[
                1,
                2,
                3,
            ],
            warmup_count=3,
        )
