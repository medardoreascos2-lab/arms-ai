import pytest

from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)


def build_window_results():

    return [
        {
            "window_index": 0,
            "training_score": 88.0,
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
            "training_score": 91.0,
            "testing_score": 85.0,
            "testing_net_pnl": 420.0,
            "testing_win_rate": 0.65,
            "testing_maximum_drawdown": 100.0,
            "best_parameters": {
                "ema": 50,
                "stop_loss": 20,
                "take_profit": 60,
            },
        },
        {
            "window_index": 2,
            "training_score": 84.0,
            "testing_score": 70.0,
            "testing_net_pnl": -50.0,
            "testing_win_rate": 0.45,
            "testing_maximum_drawdown": 280.0,
            "best_parameters": {
                "ema": 20,
                "stop_loss": 30,
                "take_profit": 60,
            },
        },
    ]


def test_builds_walk_forward_result():

    result = WalkForwardOptimizationResultV2(
        window_results=build_window_results(),
    )

    assert result.total_windows == 3
    assert result.successful_windows == 3
    assert result.failed_windows == 0


def test_calculates_average_metrics():

    result = WalkForwardOptimizationResultV2(
        window_results=build_window_results(),
    )

    assert result.average_training_score == pytest.approx(
        87.6666666667
    )

    assert result.average_testing_score == pytest.approx(
        79.0
    )

    assert result.average_testing_net_pnl == pytest.approx(
        223.3333333333
    )

    assert result.average_testing_win_rate == pytest.approx(
        0.5666666667
    )

    assert (
        result.average_testing_maximum_drawdown
        == pytest.approx(
            166.6666666667
        )
    )


def test_identifies_best_and_worst_windows():

    result = WalkForwardOptimizationResultV2(
        window_results=build_window_results(),
    )

    assert result.best_window()["window_index"] == 1
    assert result.worst_window()["window_index"] == 2


def test_identifies_most_frequent_parameters():

    result = WalkForwardOptimizationResultV2(
        window_results=build_window_results(),
    )

    assert result.most_frequent_parameters() == {
        "ema": 50,
        "stop_loss": 20,
        "take_profit": 60,
    }


def test_to_dict_returns_safe_copy():

    result = WalkForwardOptimizationResultV2(
        window_results=build_window_results(),
    )

    payload = result.to_dict()

    payload["window_results"][0][
        "testing_score"
    ] = 0.0

    assert (
        result.window_results[0]["testing_score"]
        == 82.0
    )


def test_supports_failed_windows():

    result = WalkForwardOptimizationResultV2(
        window_results=[
            {
                "window_index": 0,
                "success": True,
                "training_score": 80.0,
                "testing_score": 75.0,
                "testing_net_pnl": 100.0,
                "testing_win_rate": 0.55,
                "testing_maximum_drawdown": 100.0,
                "best_parameters": {
                    "ema": 50,
                },
            },
            {
                "window_index": 1,
                "success": False,
                "error": {
                    "type": "RuntimeError",
                    "message": "failed",
                },
            },
        ],
    )

    assert result.total_windows == 2
    assert result.successful_windows == 1
    assert result.failed_windows == 1

    assert result.average_testing_score == 75.0


def test_rejects_invalid_window_results():

    with pytest.raises(
        TypeError,
        match="window_results",
    ):
        WalkForwardOptimizationResultV2(
            window_results={},
        )


def test_rejects_non_dict_window_result():

    with pytest.raises(
        TypeError,
        match="window",
    ):
        WalkForwardOptimizationResultV2(
            window_results=[
                object(),
            ],
        )


def test_best_window_rejects_empty_successful_results():

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

    with pytest.raises(
        ValueError,
        match="exitosas",
    ):
        result.best_window()
