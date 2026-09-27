from types import SimpleNamespace

from backend.backtesting.parameter_evaluator import (
    ParameterEvaluation,
)

from backend.backtesting.parameter_evaluator_adapter_v2 import (
    ParameterEvaluatorAdapterV2,
)


class ZeroLossEvaluator:

    def evaluate(
        self,
        *,
        parameters,
        candles,
        warmup_count=0,
    ):
        statistics = SimpleNamespace(
            total_trades=10,
            winning_trades=10,
            losing_trades=0,
            breakeven_trades=0,
            gross_profit=12000.0,
            gross_loss=0.0,
            net_profit=12000.0,
            win_rate=100.0,
            profit_factor=None,
            expectancy=1200.0,
            max_drawdown=0.0,
        )

        return SimpleNamespace(
            parameters=dict(parameters),
            net_profit=12000.0,
            profit_factor=None,
            max_drawdown=0.0,
            win_rate=100.0,
            result=SimpleNamespace(
                statistics=statistics,
            ),
        )


def test_zero_loss_sample_scores_semantically_as_a_plus(
    tmp_path,
):

    adapter = ParameterEvaluatorAdapterV2(
        evaluator=ZeroLossEvaluator(),
    )

    result = adapter.evaluate(
        testing_items=[
            object()
            for _ in range(10)
        ],
        parameters={
            "ema": 5,
            "stop_loss": 30,
            "take_profit": 60,
        },
        output_directory=tmp_path,
    )

    assert result["score"] == 100.0

    assert (
        result["score_components"][
            "profit_factor"
        ]
        == 20.0
    )

    # Public/raw evaluation semantics remain unchanged.
    assert result["profit_factor"] is None
    assert result["win_rate"] == 100.0


def test_adapter_forwards_testing_warmup_size():

    class WarmupCapturingEvaluator:

        def __init__(self):
            self.calls = []

        def evaluate(
            self,
            parameters,
            candles,
            warmup_count=0,
        ):
            self.calls.append(
                {
                    "parameters":
                        dict(parameters),

                    "candles":
                        list(candles),

                    "warmup_count":
                        warmup_count,
                }
            )

            statistics = SimpleNamespace(
                total_trades=10,
                net_profit=12000.0,
                profit_factor=None,
                max_drawdown=0.0,
                win_rate=100.0,
                expectancy=1200.0,
                gross_profit=12000.0,
                gross_loss=0.0,
            )

            return ParameterEvaluation(
                parameters=dict(
                    parameters
                ),
                net_profit=12000.0,
                profit_factor=None,
                max_drawdown=0.0,
                win_rate=100.0,
                result=SimpleNamespace(
                    statistics=statistics,
                ),
            )

    evaluator = (
        WarmupCapturingEvaluator()
    )

    adapter = (
        ParameterEvaluatorAdapterV2(
            evaluator=evaluator,
        )
    )

    testing_items = [
        object()
        for _ in range(15)
    ]

    adapter.evaluate(
        testing_items=testing_items,
        testing_warmup_size=5,
        parameters={
            "ema": 5,
            "stop_loss": 30,
            "take_profit": 60,
        },
        output_directory=None,
    )

    assert (
        evaluator.calls[0][
            "warmup_count"
        ]
        == 5
    )

    assert (
        evaluator.calls[0][
            "candles"
        ]
        == testing_items
    )
