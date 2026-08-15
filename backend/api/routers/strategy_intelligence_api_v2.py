from fastapi import APIRouter


router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=[
        "Strategy Intelligence"
    ],
)


@router.get(
    "/strategy-intelligence"
)
def strategy_intelligence():

    from backend.backtesting.certification_runner_v1 import (
        CertificationRunnerV1,
    )

    from backend.backtesting.strategy_performance_tracker_v1 import (
        StrategyPerformanceTrackerV1,
    )

    from backend.backtesting.strategy_intelligence_report_v1 import (
        StrategyIntelligenceReportV1,
    )

    from backend.dashboard.strategy_intelligence_widget_v1 import (
        StrategyIntelligenceWidgetV1,
    )


    runner = CertificationRunnerV1()

    result = runner.run()


    performance = (
        StrategyPerformanceTrackerV1()
    )


    performance.add_trade(
        direction="BUY",
        entry=21000,
        stop_loss=20950,
        take_profit=21100,
        exit_price=21100,
    )


    performance.add_trade(
        direction="SELL",
        entry=21000,
        stop_loss=21050,
        take_profit=20900,
        exit_price=20900,
    )


    report = StrategyIntelligenceReportV1(
        certification=result["report"],
        metrics=result["metrics"],
        performance=performance,
    )


    widget = StrategyIntelligenceWidgetV1()

    return widget.build(
        report
    )
