import pytest

from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)
from backend.backtesting.walk_forward_report_v2 import (
    WalkForwardReportV2,
)


def build_result():

    return WalkForwardOptimizationResultV2(
        window_results=[
            {
                "window_index": 0,
                "success": True,
                "training_score": 90.0,
                "testing_score": 82.0,
                "testing_net_pnl": 300.0,
                "testing_win_rate": 0.60,
                "testing_maximum_drawdown": 120.0,
                "best_parameters": {
                    "ema": 50,
                    "stop_loss": 20,
                    "take_profit": 60,
                },
            },
            {
                "window_index": 1,
                "success": True,
                "training_score": 88.0,
                "testing_score": 78.0,
                "testing_net_pnl": 150.0,
                "testing_win_rate": 0.55,
                "testing_maximum_drawdown": 160.0,
                "best_parameters": {
                    "ema": 50,
                    "stop_loss": 20,
                    "take_profit": 60,
                },
            },
            {
                "window_index": 2,
                "success": False,
                "error": {
                    "type": "RuntimeError",
                    "message": "window failed",
                },
            },
        ],
    )


def test_builds_walk_forward_report():

    report = WalkForwardReportV2(
        optimization_result=build_result(),
    )

    assert report.total_windows == 3
    assert report.successful_windows == 2
    assert report.failed_windows == 1


def test_exposes_summary():

    report = WalkForwardReportV2(
        optimization_result=build_result(),
    )

    assert report.summary() == {
        "total_windows": 3,
        "successful_windows": 2,
        "failed_windows": 1,
        "average_training_score": 89.0,
        "average_testing_score": 80.0,
        "average_testing_net_pnl": 225.0,
        "average_testing_win_rate": pytest.approx(
            0.575
        ),
        "average_testing_maximum_drawdown": 140.0,
        "most_frequent_parameters": {
            "ema": 50,
            "stop_loss": 20,
            "take_profit": 60,
        },
    }


def test_exposes_best_and_worst_windows():

    report = WalkForwardReportV2(
        optimization_result=build_result(),
    )

    assert report.best_window()[
        "window_index"
    ] == 0

    assert report.worst_window()[
        "window_index"
    ] == 1


def test_to_dict_returns_complete_report():

    report = WalkForwardReportV2(
        optimization_result=build_result(),
    )

    payload = report.to_dict()

    assert payload["summary"][
        "total_windows"
    ] == 3

    assert payload["best_window"][
        "window_index"
    ] == 0

    assert payload["worst_window"][
        "window_index"
    ] == 1

    assert len(
        payload["window_results"]
    ) == 3


def test_to_dict_returns_safe_copy():

    report = WalkForwardReportV2(
        optimization_result=build_result(),
    )

    payload = report.to_dict()

    payload["window_results"][0][
        "testing_score"
    ] = 0.0

    assert (
        report.to_dict()["window_results"][0][
            "testing_score"
        ]
        == 82.0
    )


def test_handles_all_failed_windows():

    result = WalkForwardOptimizationResultV2(
        window_results=[
            {
                "window_index": 0,
                "success": False,
                "error": {
                    "type": "RuntimeError",
                    "message": "failed",
                },
            },
        ],
    )

    report = WalkForwardReportV2(
        optimization_result=result,
    )

    assert report.best_window() is None
    assert report.worst_window() is None

    assert report.summary()[
        "average_testing_score"
    ] == 0.0


def test_rejects_invalid_optimization_result():

    with pytest.raises(
        TypeError,
        match="WalkForwardOptimizationResultV2",
    ):
        WalkForwardReportV2(
            optimization_result={},
        )
