from backend.backtesting.backtest_report_v2 import (
    BacktestReportV2,
)


def test_build_backtest_report():

    report = BacktestReportV2(
        candles_processed=100,
        decisions=[{"id": 1}],
        trade_plans=[{"id": 2}],
        signals=[{"id": 3}],
        submission_results=[{"accepted": True}],
        position_updates=[{"updated": True}],
        trade_history=[{"trade_id": "T1"}],
        performance_metrics={
            "total_trades": 1,
            "wins": 1,
        },
        active_positions=[],
    )

    assert report.candles_processed == 100
    assert len(report.decisions) == 1
    assert len(report.trade_plans) == 1
    assert len(report.signals) == 1
    assert len(report.submission_results) == 1
    assert len(report.position_updates) == 1
    assert len(report.trade_history) == 1
    assert report.performance_metrics["wins"] == 1
    assert report.active_positions == []


def test_summary():

    report = BacktestReportV2(
        candles_processed=25,
        decisions=[1, 2],
        trade_plans=[1],
        signals=[1],
        submission_results=[1],
        position_updates=[1, 2, 3],
        trade_history=[1],
        performance_metrics={},
        active_positions=[],
    )

    summary = report.summary()

    assert summary == {
        "candles_processed": 25,
        "decisions": 2,
        "trade_plans": 1,
        "signals": 1,
        "submissions": 1,
        "position_updates": 3,
        "closed_trades": 1,
        "active_positions": 0,
    }
