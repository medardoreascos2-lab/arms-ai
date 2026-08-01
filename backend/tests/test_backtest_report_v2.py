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


def test_to_dict_returns_complete_report():

    report = BacktestReportV2(
        candles_processed=50,
        decisions=[
            {
                "action": "BUY",
            },
        ],
        trade_plans=[
            {
                "entry_price": 20000.0,
            },
        ],
        signals=[
            {
                "symbol": "NQ",
            },
        ],
        submission_results=[
            {
                "accepted": True,
            },
        ],
        position_updates=[
            {
                "updated": True,
            },
        ],
        trade_history=[
            {
                "trade_id": "T-1",
                "realized_pnl": 100.0,
            },
        ],
        performance_metrics={
            "total_trades": 1,
            "wins": 1,
            "net_pnl": 100.0,
            "equity_curve": [
                17000.0,
                17100.0,
            ],
        },
        active_positions=[],
    )

    result = report.to_dict()

    assert result == {
        "summary": {
            "candles_processed": 50,
            "decisions": 1,
            "trade_plans": 1,
            "signals": 1,
            "submissions": 1,
            "position_updates": 1,
            "closed_trades": 1,
            "active_positions": 0,
        },
        "candles_processed": 50,
        "decisions": [
            {
                "action": "BUY",
            },
        ],
        "trade_plans": [
            {
                "entry_price": 20000.0,
            },
        ],
        "signals": [
            {
                "symbol": "NQ",
            },
        ],
        "submission_results": [
            {
                "accepted": True,
            },
        ],
        "position_updates": [
            {
                "updated": True,
            },
        ],
        "trade_history": [
            {
                "trade_id": "T-1",
                "realized_pnl": 100.0,
            },
        ],
        "performance_metrics": {
            "total_trades": 1,
            "wins": 1,
            "net_pnl": 100.0,
            "equity_curve": [
                17000.0,
                17100.0,
            ],
        },
        "active_positions": [],
    }


def test_to_dict_does_not_expose_internal_collections():

    report = BacktestReportV2(
        candles_processed=1,
        decisions=[
            {
                "action": "BUY",
            },
        ],
        performance_metrics={
            "equity_curve": [
                17000.0,
            ],
        },
    )

    result = report.to_dict()

    result["decisions"][0]["action"] = "SELL"
    result["performance_metrics"][
        "equity_curve"
    ].append(18000.0)

    assert report.decisions == [
        {
            "action": "BUY",
        },
    ]

    assert report.performance_metrics == {
        "equity_curve": [
            17000.0,
        ],
    }
