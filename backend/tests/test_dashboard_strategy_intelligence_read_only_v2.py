"""Dashboard reads only serialize stored reports; fixtures are never runtime data."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import importlib
import json
from threading import Barrier
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.backtesting.certification_runner_v1 import CertificationRunnerV1
from backend.backtesting.monte_carlo_simulator_v2 import MonteCarloSimulatorV2
from backend.backtesting.scenario_generator_v1 import ScenarioGeneratorV1
from backend.backtesting.strategy_certification_pipeline_v2 import StrategyCertificationPipelineV2
from backend.backtesting.strategy_certification_report_v1 import StrategyCertificationReportV1
from backend.backtesting.strategy_metrics_engine_v1 import StrategyMetricsEngineV1
from backend.backtesting.strategy_performance_tracker_v1 import StrategyPerformanceTrackerV1
from backend.dashboard.strategy_intelligence_read_projection_v2 import project_strategy_intelligence
from backend.dashboard.strategy_intelligence_widget_v1 import StrategyIntelligenceWidgetV1
from backend.tests.test_dashboard_read_execution_safety_v2 import (
    capture, forbid_mutations, seed_existing_activity,
)


URL = "/api/v2/dashboard/strategy-intelligence"


def seal_report(stored):
    stored["provenance"]["report_sha256"] = sha256(json.dumps(
        stored["report"], sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def seed_report(app):
    """A precomputed producer-contract fixture, installed before measured GETs.

    This is not evidence that the legacy production writer has provenance;
    its unlinked objects are explicitly rejected in the tests below.
    """
    job = app.state.backtesting_job_manager_v2.create_job(job_id="stored-run-17")
    job.start()
    job.finish(report_directory="reports/previous-run")
    job.created_at = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    job.started_at = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
    job.finished_at = datetime(2026, 1, 1, 0, 3, tzinfo=timezone.utc)
    stored = {
        "report": {
            "strategy_status": "REJECTED",
            "certification": {"tests": 3, "passed": 1, "failed": 2},
            "metrics": {"average_score": 21.5, "average_probability": 42.0,
                        "buy_signals": 1, "sell_signals": 2, "no_trade": 4},
            "performance": {"trades": 3, "win_rate": 33.333, "average_rr": -0.4,
                            "net_pnl": -75.25},
        },
        "provenance": {
            "job_id": job.job_id, "strategy_id": "fixture-strategy",
            "strategy_version": "revision-17", "dataset_id": "fixture-history",
            "dataset_sha256": sha256(b"historical-dataset-test-fixture").hexdigest(),
            "generated_at": "2026-01-01T00:02:00+00:00",
            "source_kind": "HISTORICAL_BACKTEST",
        },
    }
    seal_report(stored)
    app.state.backtesting_job_executor_v2._results[job.job_id] = stored
    return job, stored


def forbid_generation(app, monkeypatch):
    orchestrator = app.state.backtesting_orchestrator_v2
    targets = [
        (importlib.import_module("backend.api.app"), ["create_app"]),
        (importlib.import_module("backend.backtesting.certification_runner_v1"), ["create_app"]),
        (FastAPI, ["__init__"]),
        (CertificationRunnerV1, ["__init__", "run", "run_scenario"]),
        (ScenarioGeneratorV1, ["bullish_a_plus_setup", "bearish_a_plus_setup",
                               "false_breakout_setup", "no_trade_setup", "_build"]),
        (StrategyPerformanceTrackerV1, ["__init__", "add_trade", "calculate"]),
        (StrategyMetricsEngineV1, ["add_result", "calculate"]),
        (StrategyCertificationReportV1, ["add_result", "summary"]),
        (StrategyIntelligenceWidgetV1, ["build"]),
        (StrategyCertificationPipelineV2, ["run"]),
        (MonteCarloSimulatorV2, ["simulate"]),
        (app.state.strategy_certification_pipeline_v2, ["run"]),
        (orchestrator, ["run", "_run_backtest"]),
        (orchestrator.backtest_engine, ["run", "run_from_csv"]),
        (orchestrator.backtest_engine.pipeline, ["run"]),
        (app.state.backtesting_job_manager_v2, ["create_job", "register_job", "delete_job", "clear"]),
        (app.state.backtesting_job_executor_v2, ["execute", "delete_result"]),
        (app.state.backtesting_job_queue_v2, ["enqueue", "dequeue", "remove", "clear"]),
        (app.state.backtesting_worker_v2, ["process_next", "process_all"]),
        (app.state.backtesting_background_worker_v2, ["start"]),
        (app.state.backtesting_controller_v2, ["start"]),
        (app.state.backtesting_metrics_provider_v2, ["add_trade", "get_metrics"]),
        (app.state.backtesting_performance_report_provider_v2, ["get_report"]),
    ]
    guards = []
    for target, methods in targets:
        for method in methods:
            guard = Mock(side_effect=AssertionError(f"GET invoked {target}.{method}"))
            monkeypatch.setattr(target, method, guard)
            guards.append(guard)
    return guards


def stored_state(app):
    return deepcopy({
        "jobs": [job.to_dict() for job in app.state.backtesting_job_manager_v2.list_jobs()],
        "reports": app.state.backtesting_job_executor_v2._results,
        "trades": app.state.backtesting_metrics_provider_v2.get_trades(),
        "queue": list(app.state.backtesting_job_queue_v2._queue),
    })


def assert_unavailable(payload, reason):
    assert payload["status"] == payload["strategy_status"] == "UNAVAILABLE"
    assert payload["data_status"] == reason
    assert payload["source"] is None
    assert payload["certification"] == {"tests": None, "passed": None, "failed": None}
    assert all(value is None for value in payload["metrics"].values())
    assert payload["performance"] == {"trades": None, "win_rate": None, "average_rr": None}


@pytest.mark.parametrize("activity", [False, True], ids=["empty-operational", "existing-operational"])
@pytest.mark.parametrize("report_state", ["absent", "valid", "incomplete"])
def test_repeated_and_concurrent_reads_have_zero_side_effects(
    tmp_path, monkeypatch, activity, report_state,
):
    app = create_app(risk_event_store_path_v2=tmp_path / "risk-events.json")
    if activity:
        seed_existing_activity(app)
    stored = None
    if report_state != "absent":
        _, stored = seed_report(app)
        if report_state == "incomplete":
            del stored["report"]["performance"]["win_rate"]
    operational_before = capture(app)
    reports_before = stored_state(app)
    client = TestClient(app)  # No startup, workers or external broker connections.
    guards = forbid_mutations(app, monkeypatch) + forbid_generation(app, monkeypatch)
    try:
        def read():
            response = client.get(URL)
            assert response.status_code == 200
            return response.json()

        first = read()
        if report_state == "valid":
            assert first == {**stored["report"], "status": "AVAILABLE",
                             "data_status": "AVAILABLE", "source": stored["provenance"]}
        else:
            assert_unavailable(first, "NO_DATA" if report_state == "absent" else "INCOMPLETE_REPORT")
        for _ in range(10):
            assert read() == first
        barrier = Barrier(8)

        def concurrent_read(_):
            barrier.wait(timeout=10)
            return read()

        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(concurrent_read, range(24)))
        assert all(response == first for response in responses)
        # A caller cannot modify any nested part of the stored report.
        first["performance"]["win_rate"] = 100
        if first["source"]:
            first["source"]["dataset_id"] = "caller mutation"
        assert read() == responses[0]
    finally:
        client.close()
    assert capture(app) == operational_before
    assert stored_state(app) == reports_before
    if stored is not None:
        assert app.state.backtesting_job_executor_v2.get_result("stored-run-17") is stored
    for guard in guards:
        guard.assert_not_called()


@pytest.mark.parametrize("damage,reason", [
    ("missing_source", "UNVERIFIABLE_PROVENANCE"),
    ("wrong_job", "UNVERIFIABLE_PROVENANCE"),
    ("missing_dataset", "UNVERIFIABLE_PROVENANCE"),
    ("missing_version", "UNVERIFIABLE_PROVENANCE"),
    ("invalid_dataset_hash", "UNVERIFIABLE_PROVENANCE"),
    ("synthetic", "UNVERIFIABLE_PROVENANCE"),
    ("tampered_performance", "UNVERIFIABLE_PROVENANCE"),
    ("invalid_timestamp", "UNVERIFIABLE_PROVENANCE"),
    ("naive_timestamp", "UNVERIFIABLE_PROVENANCE"),
    ("outside_run", "UNVERIFIABLE_PROVENANCE"),
    ("missing_start", "UNVERIFIABLE_PROVENANCE"),
    ("missing_finish", "UNVERIFIABLE_PROVENANCE"),
    ("invalid_finish", "UNVERIFIABLE_PROVENANCE"),
    ("pending_job", "INCOMPLETE_REPORT"),
    ("failed_job", "INCOMPLETE_REPORT"),
    ("missing_result", "INCOMPLETE_REPORT"),
    ("missing_certification", "INCOMPLETE_REPORT"),
    ("missing_metric", "INCOMPLETE_REPORT"),
    ("null_performance", "INCOMPLETE_REPORT"),
    ("nan", "INCOMPLETE_REPORT"),
    ("bool_trades", "INCOMPLETE_REPORT"),
    ("contradictory_certification", "INCOMPLETE_REPORT"),
    ("legacy_object", "UNVERIFIABLE_PROVENANCE"),
])
def test_unverifiable_or_incomplete_stored_reports_fail_closed(tmp_path, monkeypatch, damage, reason):
    app = create_app(risk_event_store_path_v2=tmp_path / "risk-events.json")
    job, stored = seed_report(app)
    source = stored["provenance"]
    if damage == "missing_source":
        del stored["provenance"]
    elif damage == "wrong_job":
        source["job_id"] = "other-job"
    elif damage == "missing_dataset":
        del source["dataset_id"]
    elif damage == "missing_version":
        del source["strategy_version"]
    elif damage == "invalid_dataset_hash":
        source["dataset_sha256"] = "unverified"
    elif damage == "synthetic":
        source["source_kind"] = "SYNTHETIC"
    elif damage == "tampered_performance":
        stored["report"]["performance"]["win_rate"] = 100
    elif damage in ("invalid_timestamp", "naive_timestamp", "outside_run"):
        source["generated_at"] = {"invalid_timestamp": "unknown",
                                  "naive_timestamp": "2026-01-01T00:02:00",
                                  "outside_run": "2026-01-02T00:02:00+00:00"}[damage]
    elif damage == "missing_start":
        job.started_at = None
    elif damage == "missing_finish":
        job.finished_at = None
    elif damage == "invalid_finish":
        job.finished_at = "not-a-timestamp"
    elif damage in ("pending_job", "failed_job"):
        job.status = "PENDING" if damage == "pending_job" else "FAILED"
    elif damage == "missing_result":
        app.state.backtesting_job_executor_v2._results.clear()
    elif damage == "missing_certification":
        del stored["report"]["certification"]
    elif damage == "missing_metric":
        del stored["report"]["metrics"]["average_probability"]
    elif damage == "null_performance":
        stored["report"]["performance"] = None
    elif damage == "nan":
        stored["report"]["performance"]["win_rate"] = float("nan")
    elif damage == "bool_trades":
        stored["report"]["performance"]["trades"] = True
    elif damage == "contradictory_certification":
        stored["report"]["strategy_status"] = "CERTIFIED"
    elif damage == "legacy_object":
        stored = Mock()
        app.state.backtesting_job_executor_v2._results[job.job_id] = stored
    client = TestClient(app)
    guards = forbid_mutations(app, monkeypatch) + forbid_generation(app, monkeypatch)
    try:
        response = client.get(URL)
        assert response.status_code == 200
        assert_unavailable(response.json(), reason)
    finally:
        client.close()
    if damage == "legacy_object":
        assert stored.mock_calls == []
    for guard in guards:
        guard.assert_not_called()


def test_projection_returns_detached_values_and_preserves_measured_zeroes(tmp_path):
    app = create_app(risk_event_store_path_v2=tmp_path / "risk-events.json")
    _, stored = seed_report(app)
    stored["report"]["performance"] = {"trades": 0, "win_rate": 0, "average_rr": 0}
    seal_report(stored)
    before = deepcopy(stored)
    payload = project_strategy_intelligence(
        job_manager=app.state.backtesting_job_manager_v2,
        job_executor=app.state.backtesting_job_executor_v2,
    )
    assert payload["status"] == "AVAILABLE"
    assert payload["performance"] == before["report"]["performance"]
    payload["source"]["dataset_id"] = "mutated"
    payload["performance"]["trades"] = 99
    assert stored == before


def test_missing_stores_do_not_create_them():
    app = FastAPI()
    from backend.api.routers.strategy_intelligence_api_v2 import router
    app.include_router(router)
    before = deepcopy(app.state._state)
    with TestClient(app) as client:
        assert_unavailable(client.get(URL).json(), "NO_DATA")
    assert app.state._state == before


def test_latest_completed_report_is_selected_without_generating_or_using_invalid_fallback(tmp_path, monkeypatch):
    app = create_app(risk_event_store_path_v2=tmp_path / "risk-events.json")
    old_job, stored = seed_report(app)
    manager = app.state.backtesting_job_manager_v2
    executor = app.state.backtesting_job_executor_v2
    latest_job = manager.create_job(job_id="newer-run")
    latest_job.start()
    latest_job.finish(report_directory="reports/newer-run")
    latest_job.started_at = datetime(2026, 1, 2, 0, 1, tzinfo=timezone.utc)
    latest_job.finished_at = datetime(2026, 1, 2, 0, 3, tzinfo=timezone.utc)
    latest = deepcopy(stored)
    latest["provenance"].update(job_id=latest_job.job_id, generated_at="2026-01-02T00:02:00+00:00")
    latest["report"]["strategy_status"] = "CERTIFIED"
    latest["report"]["certification"] = {"tests": 3, "passed": 3, "failed": 0}
    seal_report(latest)
    executor._results[latest_job.job_id] = latest
    client = TestClient(app)
    guards = forbid_mutations(app, monkeypatch) + forbid_generation(app, monkeypatch)
    try:
        payload = client.get(URL).json()
        assert payload["source"] == latest["provenance"]
        assert payload["strategy_status"] == "CERTIFIED"
        assert payload["certification"] == latest["report"]["certification"]
        # A corrupt newer report must not silently show an older certification.
        del latest["report"]["certification"]
        assert_unavailable(client.get(URL).json(), "INCOMPLETE_REPORT")
        assert executor.get_result(old_job.job_id) == stored
    finally:
        client.close()
    for guard in guards:
        guard.assert_not_called()
