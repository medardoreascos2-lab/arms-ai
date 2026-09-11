from __future__ import annotations

from math import isfinite

from fastapi import APIRouter

from backend.backtesting.backtesting_performance_report_v2 import (
    BacktestingPerformanceReportV2,
)

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

    Legacy generation-provider arguments remain accepted for wiring compatibility,
    but a GET must never invoke them. Unavailable projections are explicit nulls.
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
            "controller": controller.status(),
            "jobs": None,
            "queue": None,
            "worker": None,
            "metrics": None,
            "performance_report": None,
            "strategies": None,
            "strategy_ranking": None,
            "strategy_recommendation": None,
            "strategy_selection": None,
            "strategy_decision": None,
            "trade_plan": None,
            "risk_validation": None,
            "execution": None,
            "performance": None,
            "strategy_performance": None,
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

        # Metrics are derived only from trades already held by this provider.
        # Empty/incomplete history is not a measured zero-performance result.
        if metrics_provider is not None:
            try:
                metrics = metrics_provider.get_metrics()
                fields = BacktestingPerformanceReportV2.REQUIRED_FIELDS
                if (
                    isinstance(metrics, dict)
                    and fields <= metrics.keys()
                    and all(
                        isinstance(metrics[field], (int, float))
                        and not isinstance(metrics[field], bool)
                        and isfinite(metrics[field])
                        for field in fields
                    )
                    and metrics["total_trades"] > 0
                ):
                    payload["metrics"] = metrics
            except (KeyError, TypeError, ValueError, OverflowError):
                # Malformed existing data is unavailable; never synthesize trades.
                pass

        if performance_report_provider is not None and payload["metrics"] is not None:
            try:
                report = performance_report_provider.get_report()
                if isinstance(report, dict) and report.get("metrics") == payload["metrics"]:
                    payload["performance_report"] = report
            except (KeyError, TypeError, ValueError, OverflowError):
                pass

        if strategy_registry_provider is not None:
            payload["strategies"] = strategy_registry_provider.get_strategies()

        # Ranking is a pure projection of existing registry scores. Require its
        # inputs so the ranking engine cannot substitute default scores/grades.
        strategies = payload["strategies"]
        items = strategies.get("items") if isinstance(strategies, dict) else None
        if strategy_ranking_provider is not None and isinstance(items, list):
            if all(
                isinstance(item, dict)
                and item.get("grade") in {"A", "B", "C", "D", "F"}
                and all(
                    isinstance(item.get(field), (int, float))
                    and not isinstance(item[field], bool)
                    and isfinite(item[field])
                    for field in ("validation_score", "performance_score")
                )
                for item in items
            ):
                payload["strategy_ranking"] = strategy_ranking_provider.get_ranking()

        return payload

    return router
