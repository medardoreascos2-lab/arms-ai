import math
from dataclasses import dataclass

import pytest

from backend.backtesting.walk_forward_engine import (
    WalkForwardResult,
    WalkForwardWindowResult,
)
from backend.backtesting.walk_forward_report import (
    WalkForwardReport,
)


@dataclass
class DummyStatistics:
    net_profit: float
    win_rate: float = 0.0
    profit_factor: float | None = None
    max_drawdown: float = 0.0


@dataclass
class DummyBacktestResult:
    statistics: DummyStatistics


def build_walk_forward_result(
    net_profits: list[float],
) -> WalkForwardResult:
    windows = []

    for index, net_profit in enumerate(
        net_profits,
        start=1,
    ):
        start = (index - 1) * 20

        windows.append(
            WalkForwardWindowResult(
                window_number=index,
                training_start=start,
                training_end=start + 100,
                testing_start=start + 100,
                testing_end=start + 120,
                result=DummyBacktestResult(
                    statistics=DummyStatistics(
                        net_profit=net_profit,
                    )
                ),
            )
        )

    return WalkForwardResult(
        windows=windows,
    )


def test_walk_forward_report_calculates_summary():
    report = WalkForwardReport.from_result(
        build_walk_forward_result(
            [
                10.0,
                20.0,
                -5.0,
                15.0,
            ]
        )
    )

    assert report.total_windows == 4
    assert report.profitable_windows == 3
    assert report.losing_windows == 1
    assert report.breakeven_windows == 0

    assert report.total_net_profit == 40.0
    assert report.average_net_profit == 10.0
    assert report.profitable_window_rate == 75.0

    assert report.best_window_number == 2
    assert report.best_window_profit == 20.0

    assert report.worst_window_number == 3
    assert report.worst_window_profit == -5.0


def test_walk_forward_report_tracks_breakeven_windows():
    report = WalkForwardReport.from_result(
        build_walk_forward_result(
            [
                10.0,
                0.0,
                -5.0,
            ]
        )
    )

    assert report.profitable_windows == 1
    assert report.losing_windows == 1
    assert report.breakeven_windows == 1
    assert report.profitable_window_rate == pytest.approx(
        33.33,
        abs=0.01,
    )


def test_walk_forward_report_calculates_standard_deviation():
    report = WalkForwardReport.from_result(
        build_walk_forward_result(
            [
                10.0,
                20.0,
                -5.0,
                15.0,
            ]
        )
    )

    expected = math.sqrt(
        (
            (10.0 - 10.0) ** 2
            + (20.0 - 10.0) ** 2
            + (-5.0 - 10.0) ** 2
            + (15.0 - 10.0) ** 2
        )
        / 4
    )

    assert report.net_profit_std_dev == pytest.approx(
        expected
    )


def test_walk_forward_report_calculates_stability_score():
    stable = WalkForwardReport.from_result(
        build_walk_forward_result(
            [
                10.0,
                11.0,
                9.0,
                10.0,
            ]
        )
    )

    unstable = WalkForwardReport.from_result(
        build_walk_forward_result(
            [
                40.0,
                -20.0,
                35.0,
                -15.0,
            ]
        )
    )

    assert 0.0 <= stable.stability_score <= 100.0
    assert 0.0 <= unstable.stability_score <= 100.0
    assert stable.stability_score > unstable.stability_score


def test_walk_forward_report_handles_empty_result():
    report = WalkForwardReport.from_result(
        WalkForwardResult(
            windows=[],
        )
    )

    assert report.total_windows == 0
    assert report.total_net_profit == 0.0
    assert report.average_net_profit == 0.0
    assert report.profitable_window_rate == 0.0
    assert report.net_profit_std_dev == 0.0
    assert report.stability_score == 0.0
    assert report.best_window_number is None
    assert report.worst_window_number is None


def test_walk_forward_report_preserves_window_details():
    result = build_walk_forward_result(
        [
            10.0,
            -5.0,
        ]
    )

    report = WalkForwardReport.from_result(result)

    assert len(report.windows) == 2

    assert report.windows[0].window_number == 1
    assert report.windows[0].training_start == 0
    assert report.windows[0].testing_start == 100
    assert report.windows[0].net_profit == 10.0

    assert report.windows[1].window_number == 2
    assert report.windows[1].net_profit == -5.0


def test_walk_forward_report_rejects_missing_statistics():
    result = WalkForwardResult(
        windows=[
            WalkForwardWindowResult(
                window_number=1,
                training_start=0,
                training_end=100,
                testing_start=100,
                testing_end=120,
                result=object(),
            )
        ]
    )

    with pytest.raises(
        ValueError,
        match="statistics",
    ):
        WalkForwardReport.from_result(result)
