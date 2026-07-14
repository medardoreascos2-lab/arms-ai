import pytest

from backend.backtesting.statistics_engine import StatisticsEngine


def test_statistics_engine_calculates_basic_metrics():
    engine = StatisticsEngine()

    result = engine.calculate(
        pnls=[
            100.0,
            -50.0,
            150.0,
            -25.0,
        ]
    )

    assert result.total_trades == 4
    assert result.winning_trades == 2
    assert result.losing_trades == 2

    assert result.gross_profit == 250.0
    assert result.gross_loss == 75.0
    assert result.net_profit == 175.0

    assert result.win_rate == 50.0
    assert result.profit_factor == pytest.approx(
        250.0 / 75.0,
        rel=1e-2,
    )
    assert result.expectancy == pytest.approx(
        43.75,
        rel=1e-2,
    )


def test_statistics_engine_calculates_max_drawdown():
    engine = StatisticsEngine()

    result = engine.calculate(
        pnls=[
            100.0,
            50.0,
            -120.0,
            -80.0,
            200.0,
        ]
    )

    assert result.max_drawdown == 200.0


def test_statistics_engine_handles_all_winning_trades():
    engine = StatisticsEngine()

    result = engine.calculate(
        pnls=[
            100.0,
            50.0,
            25.0,
        ]
    )

    assert result.total_trades == 3
    assert result.winning_trades == 3
    assert result.losing_trades == 0
    assert result.gross_loss == 0.0
    assert result.profit_factor is None
    assert result.win_rate == 100.0


def test_statistics_engine_handles_empty_results():
    engine = StatisticsEngine()

    result = engine.calculate(pnls=[])

    assert result.total_trades == 0
    assert result.winning_trades == 0
    assert result.losing_trades == 0
    assert result.net_profit == 0.0
    assert result.win_rate == 0.0
    assert result.expectancy == 0.0
    assert result.max_drawdown == 0.0
