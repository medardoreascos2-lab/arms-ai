from dataclasses import dataclass

import pytest

from backend.backtesting.walk_forward_report import (
    WalkForwardReport,
)
from backend.backtesting.walk_forward_runner import (
    WalkForwardRunner,
)


@dataclass
class DummyWalkForwardResult:
    windows: list


class DummyLoader:
    def __init__(self, candles):
        self.candles = candles
        self.received_path = None

    def load_csv(self, file_path):
        self.received_path = file_path
        return self.candles


class DummyEngine:
    def __init__(self, result):
        self.result = result
        self.received_candles = None

    def run(self, candles):
        self.received_candles = candles
        return self.result


class DummyReportFactory:
    def __init__(self, report):
        self.report = report
        self.received_result = None

    def __call__(self, result):
        self.received_result = result
        return self.report


def test_walk_forward_runner_runs_from_csv(tmp_path):
    file_path = tmp_path / "candles.csv"
    file_path.write_text(
        "timestamp,symbol,timeframe,open,high,low,close,volume\n",
        encoding="utf-8",
    )

    candles = [1, 2, 3]
    engine_result = DummyWalkForwardResult(
        windows=[object()],
    )

    expected_report = WalkForwardReport(
        total_windows=1,
        profitable_windows=1,
        losing_windows=0,
        breakeven_windows=0,
        total_net_profit=10.0,
        average_net_profit=10.0,
        profitable_window_rate=100.0,
        net_profit_std_dev=0.0,
        stability_score=100.0,
        best_window_number=1,
        best_window_profit=10.0,
        worst_window_number=1,
        worst_window_profit=10.0,
        windows=[],
    )

    loader = DummyLoader(candles)
    engine = DummyEngine(engine_result)
    report_factory = DummyReportFactory(
        expected_report
    )

    runner = WalkForwardRunner(
        historical_data_loader=loader,
        walk_forward_engine=engine,
        report_factory=report_factory,
    )

    report = runner.run_from_csv(
        file_path=file_path,
    )

    assert report is expected_report
    assert loader.received_path == file_path
    assert engine.received_candles == candles
    assert report_factory.received_result is engine_result


def test_walk_forward_runner_runs_from_candles():
    candles = [1, 2, 3]

    engine_result = DummyWalkForwardResult(
        windows=[],
    )

    expected_report = WalkForwardReport(
        total_windows=0,
        profitable_windows=0,
        losing_windows=0,
        breakeven_windows=0,
        total_net_profit=0.0,
        average_net_profit=0.0,
        profitable_window_rate=0.0,
        net_profit_std_dev=0.0,
        stability_score=0.0,
        best_window_number=None,
        best_window_profit=None,
        worst_window_number=None,
        worst_window_profit=None,
        windows=[],
    )

    engine = DummyEngine(engine_result)
    report_factory = DummyReportFactory(
        expected_report
    )

    runner = WalkForwardRunner(
        historical_data_loader=DummyLoader([]),
        walk_forward_engine=engine,
        report_factory=report_factory,
    )

    report = runner.run(
        candles=candles,
    )

    assert report is expected_report
    assert engine.received_candles == candles
    assert report_factory.received_result is engine_result


def test_walk_forward_runner_uses_default_report_factory():
    class EngineResult:
        windows = []

    class Engine:
        def run(self, candles):
            return EngineResult()

    runner = WalkForwardRunner(
        historical_data_loader=DummyLoader([]),
        walk_forward_engine=Engine(),
    )

    report = runner.run(
        candles=[1],
    )

    assert isinstance(
        report,
        WalkForwardReport,
    )
    assert report.total_windows == 0


def test_walk_forward_runner_rejects_empty_candles():
    runner = WalkForwardRunner(
        historical_data_loader=DummyLoader([]),
        walk_forward_engine=DummyEngine(
            DummyWalkForwardResult(
                windows=[],
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="candles",
    ):
        runner.run(candles=[])


def test_walk_forward_runner_requires_engine():
    with pytest.raises(
        TypeError,
        match="walk_forward_engine",
    ):
        WalkForwardRunner(
            historical_data_loader=DummyLoader([]),
            walk_forward_engine=None,
        )
