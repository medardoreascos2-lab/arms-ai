"""Backtesting GETs only project existing data; they never run a trading pipeline."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.routers.backtesting_dashboard_api_v2 import create_backtesting_dashboard_router_v2
from backend.backtesting.backtesting_job_task_v2 import BacktestingJobTaskV2
from backend.tests.test_dashboard_read_execution_safety_v2 import (
    capture, forbid_mutations, seed_existing_activity,
)

URL = "/api/v2/backtesting/dashboard"
UNAVAILABLE = (
    "strategy_recommendation", "strategy_selection", "strategy_decision",
    "trade_plan", "risk_validation", "execution", "performance", "strategy_performance",
)


def backtesting_snapshot(app):
    state = app.state
    queue = state.backtesting_job_queue_v2
    return deepcopy({
        "registry": state.strategy_registry_v2.list(),
        "jobs": [job.to_dict() for job in state.backtesting_job_manager_v2.list_jobs()],
        "queue": [(task.job.job_id, task.output_directory) for task in queue._queue],
        "queued_ids": queue._queued_job_ids,
        "trades": state.backtesting_metrics_provider_v2.get_trades(),
        "controller": state.backtesting_controller_v2.status(),
        "worker": state.backtesting_worker_v2.status(),
        "processed": state.backtesting_worker_v2.processed_jobs,
        "last_result": state.backtesting_worker_v2.last_result,
    })


def forbid_backtesting_generation(app, monkeypatch):
    state = app.state
    targets = [
        (state.strategy_recommendation_dashboard_provider_v2, ["get_recommendation"]),
        (state.strategy_selection_dashboard_provider_v2, ["get_selection"]),
        (state.strategy_decision_dashboard_provider_v2, ["get_decision"]),
        (state.trade_plan_dashboard_provider_v2, ["get_trade_plan"]),
        (state.risk_validation_dashboard_provider_v2, ["get_risk_validation"]),
        (state.execution_dashboard_provider_v2, ["get_execution"]),
        (state.backtesting_performance_provider_v2, ["get_performance"]),
        (state.strategy_performance_dashboard_provider_v2, ["get_strategy_performance"]),
        (state.strategy_selection_service_v2, ["select", "get_selected_strategy"]),
        (state.strategy_decision_service_v2, ["decide", "get_decision"]),
        (state.strategy_decision_service_v2.decision_engine, ["decide"]),
        (state.trade_plan_service_v2, ["generate", "create_trade_plan"]),
        (state.trade_plan_service_v2.trade_plan_engine, ["generate", "create_plan"]),
        (state.risk_validation_service_v2, ["validate"]),
        (state.execution_service_v2, ["execute"]),
        (state.execution_service_v2.execution_engine, ["execute"]),
        (state.strategy_registry_v2, ["register"]),
        (state.backtesting_job_manager_v2, ["create_job", "register_job", "delete_job", "clear"]),
        (state.backtesting_job_queue_v2, ["enqueue", "dequeue", "remove", "clear"]),
        (state.backtesting_worker_v2, ["process_next", "process_all"]),
        (state.backtesting_worker_v2.executor, ["execute"]),
        (state.backtesting_controller_v2, ["start", "stop"]),
        (state.backtesting_background_worker_v2, ["start", "stop", "run_once"]),
        (state.backtesting_metrics_provider_v2, ["add_trade"]),
    ]
    for job in state.backtesting_job_manager_v2.list_jobs():
        targets.append((job, ["start", "finish", "fail", "cancel"]))
    guards = []
    for target, methods in targets:
        for method in methods:
            guard = Mock(side_effect=AssertionError(f"Backtesting GET invoked {method}"))
            monkeypatch.setattr(target, method, guard)
            guards.append(guard)
    return guards


@pytest.mark.parametrize("registry_state", ["empty", "certified", "uncertified", "incomplete"])
@pytest.mark.parametrize("history", ["empty", "recorded", "incomplete"])
@pytest.mark.parametrize("activity", [False, True], ids=["no_operation", "existing_operation"])
def test_repeated_and_concurrent_gets_preserve_state(
    tmp_path, monkeypatch, registry_state, history, activity,
):
    app = create_app(risk_event_store_path_v2=tmp_path / "risk-events.json")
    state = app.state
    if activity:
        seed_existing_activity(app)
    if registry_state != "empty":
        state.strategy_registry_v2.register({
            "strategy_id": "recorded-strategy", "name": "Recorded strategy", "version": "2",
            "status": "CERTIFIED" if registry_state == "certified" else "DRAFT",
            "grade": "B", "validation_score": 81.0,
            "performance_score": None if registry_state == "incomplete" else 63.0,
            "market_conditions": ["TRENDING", "LOW_VOLATILITY"],
            "source": {"dataset_id": "regression-dataset", "job_id": "completed-job"},
        })
    manager = state.backtesting_job_manager_v2
    job = manager.create_job(job_id="pending-job")
    task = BacktestingJobTaskV2(
        job=job, candles=[{"close": 5000}], output_directory=str(tmp_path / "pending"),
    )
    state.backtesting_job_queue_v2.enqueue(task)
    completed = manager.create_job(job_id="completed-job")
    completed.finish(report_directory=str(tmp_path / "recorded"))
    provider = state.backtesting_metrics_provider_v2
    if history == "recorded":
        # Explicit fixture history, already present before any measured GET.
        for trade_id, pnl in (("one", 321.0), ("two", -87.0), ("three", 29.0)):
            provider.add_trade({
                "trade_id": trade_id, "pnl": pnl, "strategy_id": "recorded-strategy",
                "job_id": completed.job_id, "dataset_id": "regression-dataset",
            })
    elif history == "incomplete":
        provider.add_trade({"trade_id": "missing-pnl", "job_id": completed.job_id})

    operational_before = capture(app)
    backtesting_before = backtesting_snapshot(app)
    guards = forbid_mutations(app, monkeypatch) + forbid_backtesting_generation(app, monkeypatch)
    client = TestClient(app)  # Deliberately no lifespan/background processing.
    try:
        first = client.get(URL)
        assert first.status_code == 200
        payload = first.json()
        assert all(payload[field] is None for field in UNAVAILABLE)
        assert payload["jobs"] == {
            "registered": 2, "pending": 1, "running": 0, "completed": 1, "failed": 0,
        }
        assert payload["queue"] == {"pending_tasks": 1}
        assert payload["strategies"]["items"] == backtesting_before["registry"]
        assert payload["strategies"]["certified"] == int(registry_state == "certified")
        if history == "recorded":
            assert payload["metrics"] == {
                "total_trades": 3, "winning_trades": 2, "losing_trades": 1,
                "win_rate": 2 / 3 * 100, "profit_factor": round(350 / 87, 10),
                "net_profit": 263.0, "max_drawdown": -87.0,
            }
            assert payload["performance_report"]["metrics"] == payload["metrics"]
        else:
            assert payload["metrics"] is None
            assert payload["performance_report"] is None
        if registry_state == "incomplete":
            assert payload["strategy_ranking"] is None
        elif registry_state == "empty":
            assert payload["strategy_ranking"] == {"total_strategies": 0, "ranking": []}
        else:
            ranking = payload["strategy_ranking"]["ranking"]
            assert ranking == [{**backtesting_before["registry"][0],
                                "score": 74.6, "ranking_score": 74.6, "rank": 1}]
        for _ in range(5):
            response = client.get(URL)
            assert response.status_code == 200
            assert response.json() == payload
        barrier = Barrier(8)

        def read(_):
            barrier.wait(timeout=10)
            response = client.get(URL)
            assert response.status_code == 200
            return response.json()

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(read, range(8)))
        assert all(result == payload for result in results)
    finally:
        client.close()
    assert capture(app) == operational_before
    assert backtesting_snapshot(app) == backtesting_before
    assert state.backtesting_job_queue_v2.peek() is task
    for guard in guards:
        guard.assert_not_called()


def test_missing_providers_are_explicitly_unavailable():
    app = FastAPI()
    app.include_router(create_backtesting_dashboard_router_v2(
        controller=Mock(status=Mock(return_value={"is_running": False})),
    ))
    with TestClient(app) as client:
        response = client.get(URL)
    assert response.status_code == 200
    assert response.json() == {
        "controller": {"is_running": False},
        **dict.fromkeys((*UNAVAILABLE, "jobs", "queue", "worker", "metrics",
                         "performance_report", "strategies", "strategy_ranking")),
    }


@pytest.mark.parametrize("data", [None, {}, {"total_trades": 4}, {"pnl": None},
                                   {"pnl": "invalid"}, {"pnl": float("nan")},
                                   {"pnl": float("inf")}])
def test_incomplete_metrics_do_not_trigger_report_or_fallback(tmp_path, monkeypatch, data):
    app = create_app(risk_event_store_path_v2=tmp_path / "risk-events.json")
    provider = app.state.backtesting_metrics_provider_v2
    if isinstance(data, dict) and "pnl" in data:
        provider.add_trade(data)
    else:
        monkeypatch.setattr(provider, "get_metrics", lambda: data)
    report = Mock(side_effect=AssertionError("No report without usable metrics"))
    monkeypatch.setattr(app.state.backtesting_performance_report_provider_v2, "get_report", report)
    guards = forbid_backtesting_generation(app, monkeypatch)
    client = TestClient(app)
    response = client.get(URL)
    client.close()
    assert response.status_code == 200
    assert response.json()["metrics"] is None
    assert response.json()["performance_report"] is None
    assert all(response.json()[field] is None for field in UNAVAILABLE)
    report.assert_not_called()
    for guard in guards:
        guard.assert_not_called()
