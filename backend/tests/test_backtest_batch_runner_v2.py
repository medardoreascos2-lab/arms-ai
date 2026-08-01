from dataclasses import dataclass
from pathlib import Path

import pytest

from backend.backtesting.backtest_batch_runner_v2 import (
    BacktestBatchItemV2,
    BacktestBatchResultV2,
    BacktestBatchRunnerV2,
)
from backend.backtesting.backtest_pipeline_v2 import (
    BacktestPipelineResultV2,
)
from backend.backtesting.backtest_report_v2 import (
    BacktestReportV2,
)


class FakePipelineV2:

    def __init__(
        self,
        *,
        candles_processed: int,
        total_trades: int,
        net_pnl: float,
    ) -> None:

        self.candles_processed = candles_processed
        self.total_trades = total_trades
        self.net_pnl = net_pnl
        self.calls = []

    def run(
        self,
        *,
        output_directory,
        json_filename="backtest.json",
        html_filename="backtest.html",
    ) -> BacktestPipelineResultV2:

        normalized_output_directory = Path(
            output_directory
        )

        self.calls.append(
            {
                "output_directory": (
                    normalized_output_directory
                ),
                "json_filename": json_filename,
                "html_filename": html_filename,
            }
        )

        report = BacktestReportV2(
            candles_processed=(
                self.candles_processed
            ),
            trade_history=[
                {
                    "trade_id": (
                        f"T-{index + 1}"
                    ),
                }
                for index in range(
                    self.total_trades
                )
            ],
            performance_metrics={
                "total_trades": (
                    self.total_trades
                ),
                "net_pnl": self.net_pnl,
            },
        )

        return BacktestPipelineResultV2(
            candles_processed=(
                self.candles_processed
            ),
            report=report,
            json_path=(
                normalized_output_directory
                / json_filename
            ),
            html_path=(
                normalized_output_directory
                / html_filename
            ),
        )


def build_items():

    first_pipeline = FakePipelineV2(
        candles_processed=100,
        total_trades=4,
        net_pnl=250.0,
    )

    second_pipeline = FakePipelineV2(
        candles_processed=200,
        total_trades=6,
        net_pnl=-75.0,
    )

    items = [
        BacktestBatchItemV2(
            name="nq_1m",
            pipeline=first_pipeline,
        ),
        BacktestBatchItemV2(
            name="nq_5m",
            pipeline=second_pipeline,
            json_filename="nq_5m.json",
            html_filename="nq_5m.html",
        ),
    ]

    return (
        items,
        first_pipeline,
        second_pipeline,
    )


def test_runs_multiple_backtest_pipelines(
    tmp_path,
):

    (
        items,
        first_pipeline,
        second_pipeline,
    ) = build_items()

    runner = BacktestBatchRunnerV2()

    result = runner.run(
        items=items,
        output_directory=tmp_path / "batch",
    )

    assert isinstance(
        result,
        BacktestBatchResultV2,
    )

    assert result.total_runs == 2
    assert result.successful_runs == 2
    assert result.failed_runs == 0

    assert len(result.results) == 2
    assert result.errors == []

    first_result = result.results[0]
    second_result = result.results[1]

    assert first_result["name"] == "nq_1m"
    assert first_result["success"] is True

    assert (
        first_result["pipeline_result"]
        .candles_processed
        == 100
    )

    assert (
        first_result["pipeline_result"]
        .report
        .performance_metrics["net_pnl"]
        == 250.0
    )

    assert second_result["name"] == "nq_5m"
    assert second_result["success"] is True

    assert first_pipeline.calls == [
        {
            "output_directory": (
                tmp_path
                / "batch"
                / "nq_1m"
            ),
            "json_filename": "backtest.json",
            "html_filename": "backtest.html",
        },
    ]

    assert second_pipeline.calls == [
        {
            "output_directory": (
                tmp_path
                / "batch"
                / "nq_5m"
            ),
            "json_filename": "nq_5m.json",
            "html_filename": "nq_5m.html",
        },
    ]


def test_batch_result_calculates_totals(
    tmp_path,
):

    items, _, _ = build_items()

    result = BacktestBatchRunnerV2().run(
        items=items,
        output_directory=tmp_path,
    )

    assert result.total_candles_processed == 300
    assert result.total_trades == 10
    assert result.total_net_pnl == 175.0


class FailingPipelineV2:

    def run(
        self,
        *,
        output_directory,
        json_filename="backtest.json",
        html_filename="backtest.html",
    ):

        raise RuntimeError(
            "pipeline failed"
        )


def test_continues_when_one_pipeline_fails(
    tmp_path,
):

    successful_pipeline = FakePipelineV2(
        candles_processed=50,
        total_trades=2,
        net_pnl=100.0,
    )

    items = [
        BacktestBatchItemV2(
            name="successful",
            pipeline=successful_pipeline,
        ),
        BacktestBatchItemV2(
            name="failed",
            pipeline=FailingPipelineV2(),
        ),
    ]

    result = BacktestBatchRunnerV2(
        continue_on_error=True,
    ).run(
        items=items,
        output_directory=tmp_path,
    )

    assert result.total_runs == 2
    assert result.successful_runs == 1
    assert result.failed_runs == 1

    assert len(result.results) == 1
    assert len(result.errors) == 1

    error = result.errors[0]

    assert error["name"] == "failed"
    assert error["error_type"] == "RuntimeError"
    assert error["message"] == "pipeline failed"


def test_stops_when_pipeline_fails_and_continue_is_false(
    tmp_path,
):

    runner = BacktestBatchRunnerV2(
        continue_on_error=False,
    )

    items = [
        BacktestBatchItemV2(
            name="failed",
            pipeline=FailingPipelineV2(),
        ),
    ]

    with pytest.raises(
        RuntimeError,
        match="pipeline failed",
    ):
        runner.run(
            items=items,
            output_directory=tmp_path,
        )


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
    ],
)
def test_batch_item_rejects_empty_name(
    name,
):

    with pytest.raises(
        ValueError,
        match="name",
    ):
        BacktestBatchItemV2(
            name=name,
            pipeline=FakePipelineV2(
                candles_processed=1,
                total_trades=0,
                net_pnl=0.0,
            ),
        )


def test_batch_item_rejects_invalid_pipeline():

    with pytest.raises(
        TypeError,
        match="run",
    ):
        BacktestBatchItemV2(
            name="invalid",
            pipeline=object(),
        )


def test_runner_rejects_empty_items(
    tmp_path,
):

    runner = BacktestBatchRunnerV2()

    with pytest.raises(
        ValueError,
        match="items",
    ):
        runner.run(
            items=[],
            output_directory=tmp_path,
        )
