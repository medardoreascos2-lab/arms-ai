from backend.backtesting.backtest_batch_runner_v2 import (
    BacktestBatchResultV2,
)
from backend.backtesting.backtest_comparison_report_v2 import (
    BacktestComparisonReportV2,
)
from backend.backtesting.backtest_pipeline_v2 import (
    BacktestPipelineResultV2,
)
from backend.backtesting.backtest_report_v2 import (
    BacktestReportV2,
)


def make_pipeline_result(
    *,
    candles: int,
    trades: int,
    net_pnl: float,
    win_rate: float,
    profit_factor: float,
    drawdown: float,
    expectancy: float,
):

    report = BacktestReportV2(
        candles_processed=candles,
        trade_history=[
            {"trade_id": f"T{i}"}
            for i in range(trades)
        ],
        performance_metrics={
            "total_trades": trades,
            "net_pnl": net_pnl,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "maximum_drawdown": drawdown,
            "expectancy": expectancy,
        },
    )

    return BacktestPipelineResultV2(
        candles_processed=candles,
        report=report,
        json_path="a.json",
        html_path="a.html",
    )


def build_batch():

    return BacktestBatchResultV2(
        total_runs=3,
        successful_runs=3,
        failed_runs=0,
        results=[
            {
                "name": "EMA_20",
                "success": True,
                "pipeline_result": make_pipeline_result(
                    candles=500,
                    trades=12,
                    net_pnl=450,
                    win_rate=0.58,
                    profit_factor=1.60,
                    drawdown=120,
                    expectancy=37.5,
                ),
            },
            {
                "name": "EMA_50",
                "success": True,
                "pipeline_result": make_pipeline_result(
                    candles=500,
                    trades=8,
                    net_pnl=810,
                    win_rate=0.75,
                    profit_factor=2.35,
                    drawdown=80,
                    expectancy=101.2,
                ),
            },
            {
                "name": "VWAP",
                "success": True,
                "pipeline_result": make_pipeline_result(
                    candles=500,
                    trades=15,
                    net_pnl=-120,
                    win_rate=0.40,
                    profit_factor=0.82,
                    drawdown=300,
                    expectancy=-8,
                ),
            },
        ],
    )


def test_build_comparison():

    comparison = (
        BacktestComparisonReportV2.from_batch_result(
            build_batch()
        )
    )

    assert comparison.total_strategies == 3


def test_best_by_net_pnl():

    comparison = (
        BacktestComparisonReportV2.from_batch_result(
            build_batch()
        )
    )

    best = comparison.best_by("net_pnl")

    assert best["name"] == "EMA_50"


def test_best_by_profit_factor():

    comparison = (
        BacktestComparisonReportV2.from_batch_result(
            build_batch()
        )
    )

    best = comparison.best_by(
        "profit_factor"
    )

    assert best["name"] == "EMA_50"


def test_rank_by_win_rate():

    comparison = (
        BacktestComparisonReportV2.from_batch_result(
            build_batch()
        )
    )

    ranking = comparison.rank_by(
        "win_rate"
    )

    assert [
        row["name"]
        for row in ranking
    ] == [
        "EMA_50",
        "EMA_20",
        "VWAP",
    ]


def test_to_dict():

    comparison = (
        BacktestComparisonReportV2.from_batch_result(
            build_batch()
        )
    )

    payload = comparison.to_dict()

    assert payload["total_strategies"] == 3
    assert len(payload["strategies"]) == 3


def test_rejects_invalid_metric():

    comparison = (
        BacktestComparisonReportV2.from_batch_result(
            build_batch()
        )
    )

    try:
        comparison.best_by("abc")
    except ValueError:
        pass
    else:
        raise AssertionError()


def test_zero_loss_profitable_strategy_uses_semantic_profit_factor_for_scoring():
    report = BacktestReportV2(
        candles_processed=5600,
        trade_history=[
            {
                "trade_id": f"T{i}"
            }
            for i in range(10)
        ],
        performance_metrics={
            "total_trades": 10,
            "net_pnl": 12000.0,
            "win_rate": 1.0,
            "gross_profit": 12000.0,
            "gross_loss": 0.0,
            "profit_factor": None,
            "maximum_drawdown": 0.0,
            "expectancy": 1200.0,
        },
    )

    pipeline_result = BacktestPipelineResultV2(
        candles_processed=5600,
        report=report,
        json_path="a.json",
        html_path="a.html",
    )

    batch = BacktestBatchResultV2(
        total_runs=1,
        successful_runs=1,
        failed_runs=0,
        results=[
            {
                "name": "ZERO_LOSS",
                "success": True,
                "pipeline_result": (
                    pipeline_result
                ),
            }
        ],
        errors=[],
        total_candles_processed=5600,
        total_trades=10,
        total_net_pnl=12000.0,
    )

    comparison = (
        BacktestComparisonReportV2
        .from_batch_result(
            batch
        )
    )

    # Public/reportable semantics stay unchanged.
    assert (
        comparison.strategies[0][
            "profit_factor"
        ]
        is None
    )

    assert (
        comparison.strategies[0][
            "gross_profit"
        ]
        == 12000.0
    )

    assert (
        comparison.strategies[0][
            "gross_loss"
        ]
        == 0.0
    )

    from backend.backtesting.backtest_composite_score_v2 import (
        BacktestCompositeScoreV2,
    )

    ranking = comparison.rank_by_score(
        BacktestCompositeScoreV2()
    )

    assert ranking[0]["score"] == 100.0
    assert ranking[0]["grade"] == "A+"

    # Ranking result must also preserve public PF.
    assert (
        ranking[0]["profit_factor"]
        is None
    )

    assert (
        "LOW_PROFIT_FACTOR"
        not in ranking[0]["weaknesses"]
    )
