from pathlib import Path

import pytest

from backend.backtesting.backtest_pipeline_v2 import (
    BacktestPipelineResultV2,
    BacktestPipelineV2,
)
from backend.backtesting.backtest_report_v2 import (
    BacktestReportV2,
)


class FakeBacktestSessionV2:

    def __init__(self) -> None:
        self.run_calls = 0
        self.run_kwargs = []
        self.build_report_calls = []
        self.loaded_candles = []

        class Replay:

            def __init__(
                replay_self,
                owner,
            ):
                replay_self.owner = owner

            def load(
                replay_self,
                candles,
            ):
                replay_self.owner.loaded_candles.append(
                    list(candles)
                )

        class Runner:
            pass

        self.backtest_runner_v2 = Runner()

        self.backtest_runner_v2.replay_engine_v2 = (
            Replay(self)
        )

    def run(
        self,
        *,
        execution_candles=None,
        minimum_candles=1,
    ) -> int:
        self.run_calls += 1
        self.run_kwargs.append(
            {
                "execution_candles":
                    execution_candles,
                "minimum_candles":
                    minimum_candles,
            }
        )
        return 5

    def build_report(
        self,
        *,
        candles_processed,
    ) -> BacktestReportV2:

        self.build_report_calls.append(
            candles_processed
        )

        return BacktestReportV2(
            candles_processed=(
                candles_processed
            ),
            decisions=[
                {
                    "action": "BUY",
                },
            ],
            trade_history=[
                {
                    "trade_id": "T-1",
                    "result": "WIN",
                },
            ],
            performance_metrics={
                "total_trades": 1,
                "wins": 1,
            },
        )


class FakeExporterV2:

    def __init__(self) -> None:
        self.calls = []

    def export(
        self,
        *,
        report,
        output_path,
    ) -> Path:

        normalized_path = Path(
            output_path
        )

        self.calls.append(
            {
                "report": report,
                "output_path": normalized_path,
            }
        )

        return normalized_path


def build_pipeline():

    session = FakeBacktestSessionV2()
    json_exporter = FakeExporterV2()
    html_exporter = FakeExporterV2()

    pipeline = BacktestPipelineV2(
        backtest_session_v2=session,
        json_exporter_v2=json_exporter,
        html_exporter_v2=html_exporter,
    )

    return (
        pipeline,
        session,
        json_exporter,
        html_exporter,
    )


def test_pipeline_runs_session_and_exports_report(
    tmp_path,
):

    (
        pipeline,
        session,
        json_exporter,
        html_exporter,
    ) = build_pipeline()

    result = pipeline.run(
        output_directory=tmp_path / "reports",
    )

    assert isinstance(
        result,
        BacktestPipelineResultV2,
    )

    assert result.candles_processed == 5

    assert isinstance(
        result.report,
        BacktestReportV2,
    )

    assert result.report.summary() == {
        "candles_processed": 5,
        "decisions": 1,
        "trade_plans": 0,
        "signals": 0,
        "submissions": 0,
        "position_updates": 0,
        "closed_trades": 1,
        "active_positions": 0,
    }

    assert result.json_path == (
        tmp_path
        / "reports"
        / "backtest.json"
    )

    assert result.html_path == (
        tmp_path
        / "reports"
        / "backtest.html"
    )

    assert session.run_calls == 1

    assert session.run_kwargs == [
        {
            "execution_candles": None,
            "minimum_candles": 1,
        }
    ]

    assert session.build_report_calls == [5]

    assert len(json_exporter.calls) == 1
    assert len(html_exporter.calls) == 1

    assert (
        json_exporter.calls[0]["report"]
        is result.report
    )

    assert (
        html_exporter.calls[0]["report"]
        is result.report
    )


def test_pipeline_accepts_custom_filenames(
    tmp_path,
):

    pipeline, _, _, _ = build_pipeline()

    result = pipeline.run(
        output_directory=tmp_path,
        json_filename="nq_result.json",
        html_filename="nq_result.html",
    )

    assert result.json_path == (
        tmp_path
        / "nq_result.json"
    )

    assert result.html_path == (
        tmp_path
        / "nq_result.html"
    )


@pytest.mark.parametrize(
    "filename",
    [
        "",
        "   ",
    ],
)
def test_pipeline_rejects_empty_filenames(
    tmp_path,
    filename,
):

    pipeline, _, _, _ = build_pipeline()

    with pytest.raises(
        ValueError,
        match="filename",
    ):
        pipeline.run(
            output_directory=tmp_path,
            json_filename=filename,
        )


def test_pipeline_rejects_invalid_session():

    with pytest.raises(
        TypeError,
        match="run",
    ):
        BacktestPipelineV2(
            backtest_session_v2=object(),
            json_exporter_v2=FakeExporterV2(),
            html_exporter_v2=FakeExporterV2(),
        )


def test_pipeline_rejects_invalid_exporter():

    with pytest.raises(
        TypeError,
        match="export",
    ):
        BacktestPipelineV2(
            backtest_session_v2=(
                FakeBacktestSessionV2()
            ),
            json_exporter_v2=object(),
            html_exporter_v2=FakeExporterV2(),
        )


def test_pipeline_uses_explicit_single_pass_when_candles_are_supplied(
    tmp_path,
):

    from datetime import datetime, timedelta

    from backend.models.candle import Candle

    pipeline, session, _, _ = build_pipeline()

    candles = [
        Candle(
            symbol="NQ",
            timeframe="1m",
            open=20000.0 + index,
            high=20001.0 + index,
            low=19999.0 + index,
            close=20000.5 + index,
            volume=1000.0,
            timestamp=(
                datetime(2026, 1, 1)
                + timedelta(minutes=index)
            ),
        )
        for index in range(5)
    ]

    pipeline.run(
        output_directory=tmp_path,
        candles=candles,
    )

    assert session.run_calls == 1

    assert session.loaded_candles == [
        candles
    ]

    assert (
        session.run_kwargs[0][
            "execution_candles"
        ]
        == candles
    )

    assert (
        session.run_kwargs[0][
            "minimum_candles"
        ]
        == 1
    )


def test_pipeline_rejects_unsorted_candles_before_execution(
    tmp_path,
):

    from datetime import datetime, timedelta

    from backend.models.candle import Candle

    pipeline, session, _, _ = build_pipeline()

    first = Candle(
        symbol="NQ",
        timeframe="1m",
        open=20000.0,
        high=20001.0,
        low=19999.0,
        close=20000.5,
        volume=1000.0,
        timestamp=datetime(2026, 1, 1, 0, 1),
    )

    second = Candle(
        symbol="NQ",
        timeframe="1m",
        open=20001.0,
        high=20002.0,
        low=20000.0,
        close=20001.5,
        volume=1000.0,
        timestamp=datetime(2026, 1, 1, 0, 0),
    )

    with pytest.raises(
        ValueError,
        match="chronological",
    ):
        pipeline.run(
            output_directory=tmp_path,
            candles=[
                first,
                second,
            ],
        )

    assert session.run_calls == 0
