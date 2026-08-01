from backend.backtesting.backtest_batch_runner_v2 import (
    BacktestBatchResultV2,
)
from backend.backtesting.backtest_comparison_report_v2 import (
    BacktestComparisonReportV2,
)
from backend.backtesting.backtest_composite_score_v2 import (
    BacktestCompositeScoreV2,
)
from backend.backtesting.backtest_pipeline_v2 import (
    BacktestPipelineResultV2,
)
from backend.backtesting.backtest_report_v2 import (
    BacktestReportV2,
)


def pipeline(name, pnl, win_rate, pf):

    report = BacktestReportV2(
        candles_processed=100,
        trade_history=[
            {"trade_id": "T1"},
            {"trade_id": "T2"},
            {"trade_id": "T3"},
            {"trade_id": "T4"},
            {"trade_id": "T5"},
            {"trade_id": "T6"},
            {"trade_id": "T7"},
            {"trade_id": "T8"},
            {"trade_id": "T9"},
            {"trade_id": "T10"},
        ],
        performance_metrics={
            "total_trades": 10,
            "net_pnl": pnl,
            "win_rate": win_rate,
            "profit_factor": pf,
            "expectancy": pnl / 10,
            "maximum_drawdown": 150,
        },
    )

    return {
        "name": name,
        "success": True,
        "pipeline_result": BacktestPipelineResultV2(
            candles_processed=100,
            report=report,
            json_path="a.json",
            html_path="a.html",
        ),
    }


def build_batch():

    return BacktestBatchResultV2(
        total_runs=3,
        successful_runs=3,
        failed_runs=0,
        results=[
            pipeline(
                "EMA20",
                300,
                0.55,
                1.30,
            ),
            pipeline(
                "EMA50",
                1200,
                0.72,
                2.40,
            ),
            pipeline(
                "VWAP",
                -200,
                0.35,
                0.80,
            ),
        ],
    )


def test_rank_by_score():

    comparison = (
        BacktestComparisonReportV2.from_batch_result(
            build_batch()
        )
    )

    scorer = BacktestCompositeScoreV2()

    ranking = comparison.rank_by_score(
        scorer
    )

    assert ranking[0]["name"] == "EMA50"
    assert ranking[-1]["name"] == "VWAP"

    assert (
        ranking[0]["score"]
        >
        ranking[1]["score"]
    )


def test_best_overall():

    comparison = (
        BacktestComparisonReportV2.from_batch_result(
            build_batch()
        )
    )

    scorer = BacktestCompositeScoreV2()

    best = comparison.best_overall(
        scorer
    )

    assert best["name"] == "EMA50"

    assert best["grade"] in {
        "A",
        "A+",
    }
