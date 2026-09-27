from math import isinf

from backend.models.backtest_statistics import (
    BacktestStatistics,
)

from backend.backtesting.backtest_score_metrics_v2 import (
    build_backtest_score_metrics_v2,
)


def test_normalizes_percentage_win_rate():

    statistics = BacktestStatistics(
        total_trades=10,
        winning_trades=7,
        losing_trades=3,
        gross_profit=2100.0,
        gross_loss=900.0,
        net_profit=1200.0,
        win_rate=70.0,
        profit_factor=2.3333,
        expectancy=120.0,
        max_drawdown=300.0,
    )

    metrics = build_backtest_score_metrics_v2(
        statistics
    )

    assert metrics["win_rate"] == 0.70
    assert metrics["profit_factor"] == 2.3333
    assert metrics["total_trades"] == 10


def test_preserves_fractional_win_rate():

    statistics = BacktestStatistics(
        total_trades=10,
        winning_trades=7,
        losing_trades=3,
        gross_profit=2100.0,
        gross_loss=900.0,
        net_profit=1200.0,
        win_rate=0.70,
        profit_factor=2.3333,
        expectancy=120.0,
        max_drawdown=300.0,
    )

    metrics = build_backtest_score_metrics_v2(
        statistics
    )

    assert metrics["win_rate"] == 0.70


def test_zero_loss_profitable_sample_has_infinite_pf_for_scoring():

    statistics = BacktestStatistics(
        total_trades=10,
        winning_trades=10,
        losing_trades=0,
        gross_profit=12000.0,
        gross_loss=0.0,
        net_profit=12000.0,
        win_rate=100.0,
        profit_factor=None,
        expectancy=1200.0,
        max_drawdown=0.0,
    )

    metrics = build_backtest_score_metrics_v2(
        statistics
    )

    assert metrics["win_rate"] == 1.0
    assert isinf(
        metrics["profit_factor"]
    )
    assert metrics["net_pnl"] == 12000.0
    assert metrics["maximum_drawdown"] == 0.0
    assert metrics["total_trades"] == 10


def test_empty_sample_does_not_receive_infinite_pf():

    statistics = BacktestStatistics()

    metrics = build_backtest_score_metrics_v2(
        statistics
    )

    assert metrics["profit_factor"] == 0.0
    assert metrics["win_rate"] == 0.0
    assert metrics["total_trades"] == 0


def test_none_pf_with_no_profit_is_not_treated_as_infinite():

    statistics = BacktestStatistics(
        total_trades=3,
        winning_trades=0,
        losing_trades=0,
        breakeven_trades=3,
        gross_profit=0.0,
        gross_loss=0.0,
        net_profit=0.0,
        win_rate=0.0,
        profit_factor=None,
        expectancy=0.0,
        max_drawdown=0.0,
    )

    metrics = build_backtest_score_metrics_v2(
        statistics
    )

    assert metrics["profit_factor"] == 0.0
