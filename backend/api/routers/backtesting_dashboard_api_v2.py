from __future__ import annotations

from fastapi import APIRouter

from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)
from backend.backtesting.backtesting_job_v2 import (
    BacktestingJobStatusV2,
)


def create_backtesting_dashboard_router_v2(
    *,
    controller,
    job_manager: BacktestingJobManagerV2 | None = None,
    job_queue=None,
    worker=None,
    metrics_provider=None,
    performance_report_provider=None,
    strategy_registry_provider=None,
    strategy_recommendation_provider=None,
    strategy_decision_provider=None,
    trade_plan_provider=None,
    risk_validation_provider=None,
    execution_provider=None,
    performance_provider=None,
    strategy_performance_provider=None,
    strategy_ranking_provider=None,
    strategy_selection_provider=None,
) -> APIRouter:
    """
    Router REST para exponer un resumen operativo
    del subsistema de backtesting.
    """

    if not callable(
        getattr(
            controller,
            "status",
            None,
        )
    ):
        raise TypeError(
            "controller debe implementar status()."
        )

    if (
        job_manager is not None
        and not isinstance(
            job_manager,
            BacktestingJobManagerV2,
        )
    ):
        raise TypeError(
            "job_manager debe ser "
            "BacktestingJobManagerV2."
        )

    if (
        job_queue is not None
        and not callable(
            getattr(
                job_queue,
                "__len__",
                None,
            )
        )
    ):
        raise TypeError(
            "job_queue debe implementar __len__()."
        )

    if (
        worker is not None
        and not callable(
            getattr(
                worker,
                "status",
                None,
            )
        )
    ):
        raise TypeError(
            "worker debe implementar status()."
        )

    if (
        metrics_provider is not None
        and not callable(
            getattr(
                metrics_provider,
                "get_metrics",
                None,
            )
        )
    ):
        raise TypeError(
            "metrics_provider debe implementar get_metrics()."
        )


    if (
        performance_report_provider is not None
        and not callable(
            getattr(
                performance_report_provider,
                "get_report",
                None,
            )
        )
    ):
        raise TypeError(
            "performance_report_provider debe implementar get_report()."
        )

    if (
        strategy_registry_provider is not None
        and not callable(
            getattr(
                strategy_registry_provider,
                "get_strategies",
                None,
            )
        )
    ):
        raise TypeError(
            "strategy_registry_provider debe implementar get_strategies()."
        )

    if (
        strategy_recommendation_provider is not None
        and not callable(
            getattr(
                strategy_recommendation_provider,
                "get_recommendation",
                None,
            )
        )
    ):
        raise TypeError(
            "strategy_recommendation_provider debe implementar get_recommendation()."
        )

    if (
        trade_plan_provider is not None
        and not callable(
            getattr(
                trade_plan_provider,
                "get_trade_plan",
                None,
            )
        )
    ):
        raise TypeError(
            "trade_plan_provider debe implementar get_trade_plan()."
        )

    if (
        strategy_decision_provider is not None
        and not callable(
            getattr(
                strategy_decision_provider,
                "get_decision",
                None,
            )
        )
    ):
        raise TypeError(
            "strategy_decision_provider debe implementar get_decision()."
        )

    router = APIRouter(
        prefix="/api/v2/backtesting",
        tags=[
            "backtesting-dashboard-v2",
        ],
    )

    @router.get("/dashboard")
    def get_dashboard():

        payload = {
            "controller": (
                controller.status()
            ),
        }

        if job_manager is not None:

            jobs = job_manager.list_jobs()

            counts = {
                "registered": len(jobs),
                "pending": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
            }

            for job in jobs:

                if (
                    job.status
                    == BacktestingJobStatusV2.PENDING
                ):
                    counts["pending"] += 1

                elif (
                    job.status
                    == BacktestingJobStatusV2.RUNNING
                ):
                    counts["running"] += 1

                elif (
                    job.status
                    == BacktestingJobStatusV2.COMPLETED
                ):
                    counts["completed"] += 1

                elif (
                    job.status
                    == BacktestingJobStatusV2.FAILED
                ):
                    counts["failed"] += 1

            payload["jobs"] = counts

        if job_queue is not None:
            payload["queue"] = {
                "pending_tasks": len(
                    job_queue
                ),
            }

        if worker is not None:
            payload["worker"] = (
                worker.status()
            )

        if metrics_provider is not None:
            payload["metrics"] = (
                metrics_provider.get_metrics()
            )

        if performance_report_provider is not None:
            payload["performance_report"] = (
                performance_report_provider.get_report()
            )

        if strategy_registry_provider is not None:
            payload["strategies"] = (
                strategy_registry_provider.get_strategies()
            )

        if strategy_recommendation_provider is not None:
            payload["strategy_recommendation"] = (
                strategy_recommendation_provider.get_recommendation()
            )

        payload["trade_plan"] = None
        payload["risk_validation"] = None
        payload["execution"] = None


        if trade_plan_provider is not None:
            payload["trade_plan"] = (
                trade_plan_provider.get_trade_plan()
            )

        if risk_validation_provider is not None:
            payload["risk_validation"] = (
                risk_validation_provider.get_risk_validation()
            )

        if execution_provider is not None:
            payload["execution"] = (
                execution_provider.get_execution()
            )


        if performance_provider is not None:
            payload["performance"] = (
                performance_provider.get_performance()
            )

        if strategy_performance_provider is not None:
            payload["strategy_performance"] = (
                strategy_performance_provider
                .get_strategy_performance()
            )


        if strategy_ranking_provider is not None:
            payload["strategy_ranking"] = (
                strategy_ranking_provider
                .get_ranking()
            )


        if strategy_selection_provider is not None:
            payload["strategy_selection"] = (
                strategy_selection_provider
                .get_selection(
                    market_context={}
                )
            )


        if strategy_decision_provider is not None:
            payload["strategy_decision"] = (
                strategy_decision_provider.get_decision()
            )

        return payload

    return router
