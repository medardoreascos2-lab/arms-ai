"""Only explicit test setup prepares orders; measured dashboard reads never do."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from threading import Barrier
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.routers.execution_manager_api_v2 import router
from backend.dashboard.execution_manager_read_projection_v2 import project_execution_manager
from backend.execution.execution_manager_engine import ExecutionManagerEngine, ExecutionPlan
from backend.execution.execution_manager_v2 import ExecutionManagerV2
from backend.services.live_analysis_store import LiveAnalysisStore
from backend.services.live_market_analysis_service import LiveMarketAnalysisService
from backend.signals.signal_generator_v2 import SignalGeneratorV2
from backend.tests.test_dashboard_read_execution_safety_v2 import (
    capture, forbid_mutations, seed_existing_activity,
)


URL = "/api/v2/dashboard/execution-manager"


def produce_analysis(manager, *, blocked=False, symbol="MES", order_type="MARKET"):
    """Use the real signal/order producers before reads, with explicit test inputs.

    This exercises an existing prepared order, without invoking a broker or
    changing production writers. The inputs are fixtures, not market evidence.
    """
    signal = SignalGeneratorV2(
        minimum_probability=0.8, minimum_confluence_score=0.8, allowed_grades={"A+"},
    ).generate(
        symbol=symbol, timeframe="5m",
        trade_plan={"approved": not blocked, "direction": "SHORT", "contracts": 1,
                    "entry_price": 5378.25, "stop_loss": 5384.0, "take_profit": 5359.0,
                    "probability": 0.93, "confluence_score": 0.91, "grade": "A+"},
        trade_validation={"approved": not blocked, "warnings": ["test-source-warning"]},
    )
    plan = manager.prepare_order(signal=signal, order_type=order_type)
    return {
        "symbol": symbol, "timeframe": "5m", "current_price": 5378.25,
        "trend": "BAJISTA", "decision": {}, "probability": {}, "risk": {},
        "analyzed_at": datetime(2026, 9, 10, 14, 30, tzinfo=timezone.utc),
        "signal_v2": signal, "prepared_order_v2": plan,
    }


def forbid_plan_generation(monkeypatch, store):
    targets = [
        (ExecutionManagerEngine, "prepare_order"),
        (ExecutionManagerEngine, "__init__"),
        (ExecutionPlan, "__init__"),
        (ExecutionManagerV2, "prepare_order"),
        (SignalGeneratorV2, "generate"),
        (LiveMarketAnalysisService, "analyze"),
        (store, "save"), (store, "clear"),
        (FastAPI, "__init__"),
    ]
    guards = []
    for target, method in targets:
        guard = Mock(side_effect=AssertionError(f"GET invoked {method}"))
        monkeypatch.setattr(target, method, guard)
        guards.append(guard)
    return guards


def assert_unavailable(payload, reason):
    assert payload["status"] == "UNAVAILABLE"
    assert payload["data_status"] == reason
    assert payload["validation"] == []  # No invented validation successes.
    for name in ("source", "symbol", "direction", "order_type", "contracts", "entry",
                 "stop_loss", "take_profit", "risk_amount", "approved", "order_id", "prepared_order"):
        assert payload[name] is None


def assert_existing_plan(payload, analysis):
    plan = analysis["prepared_order_v2"]
    assert payload["data_status"] == "AVAILABLE"
    assert payload["prepared_order"] == plan
    assert payload["status"] == plan["status"]
    assert payload["approved"] is plan["approved"]
    assert payload["order_type"] == plan["order_type"]
    assert payload["entry"] == plan["entry_price"]
    assert payload["stop_loss"] == plan["stop_loss"]
    assert payload["take_profit"] == plan["take_profit"]
    assert payload["contracts"] == plan["quantity"]
    assert payload["source"] == {
        "store": "live_analysis_store", "symbol": analysis["symbol"],
        "timeframe": analysis["timeframe"], "analyzed_at": analysis["analyzed_at"].isoformat(),
        "field": "prepared_order_v2", "signal": analysis["signal_v2"],
    }
    assert payload["risk_amount"] is None  # No calculation from price distances.
    assert payload["order_id"] is None  # Preparing a plan does not imply an order.
    assert payload["validation"] == []  # Not invented from approval or no blockers.
    assert "execution_status" not in payload


@pytest.mark.parametrize("activity", [False, True], ids=["empty-operational", "existing-operational"])
@pytest.mark.parametrize("plan_state", ["absent", "ready", "blocked", "incomplete"])
def test_repeated_and_concurrent_reads_never_prepare_or_execute(tmp_path, monkeypatch, activity, plan_state):
    app = create_app(risk_event_store_path_v2=tmp_path / "risk-events.json")
    if activity:
        seed_existing_activity(app)
    store = app.state.live_analysis_store
    if plan_state != "absent":
        analysis = produce_analysis(app.state.execution_manager_v2, blocked=plan_state == "blocked")
        if plan_state == "incomplete":
            del analysis["prepared_order_v2"]["entry_price"]
        store.save(analysis)
    before = deepcopy(store._storage)
    originals = dict(store._storage)
    operational_before = capture(app)
    client = TestClient(app)  # No startup workers or external broker connections.
    guards = forbid_mutations(app, monkeypatch) + forbid_plan_generation(monkeypatch, store)
    try:
        def read():
            response = client.get(URL)
            assert response.status_code == 200
            return response.json()

        first = read()
        if plan_state in ("ready", "blocked"):
            assert_existing_plan(first, analysis)
        else:
            assert_unavailable(first, "NO_DATA" if plan_state == "absent" else "INCOMPLETE_PLAN")
        for _ in range(10):
            assert read() == first
        barrier = Barrier(8)

        def concurrent_read(_):
            barrier.wait(timeout=10)
            return read()

        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(concurrent_read, range(24)))
        assert all(payload == first for payload in responses)
        assert read() == first
    finally:
        client.close()
    assert store._storage == before
    assert all(store._storage[key] is value for key, value in originals.items())
    assert capture(app) == operational_before
    for guard in guards:
        guard.assert_not_called()


@pytest.fixture
def stored_analysis():
    store = LiveAnalysisStore()
    analysis = produce_analysis(ExecutionManagerV2(execution_mode="PAPER", maximum_contracts=3))
    return store, analysis


@pytest.mark.parametrize("damage,reason", [
    ("missing_plan", "NO_DATA"),
    ("missing_signal", "UNVERIFIABLE_PROVENANCE"),
    ("missing_timestamp", "UNVERIFIABLE_PROVENANCE"),
    ("naive_timestamp", "UNVERIFIABLE_PROVENANCE"),
    ("invalid_timestamp", "UNVERIFIABLE_PROVENANCE"),
    ("wrong_symbol", "UNVERIFIABLE_PROVENANCE"),
    ("wrong_timeframe", "UNVERIFIABLE_PROVENANCE"),
    ("wrong_direction", "UNVERIFIABLE_PROVENANCE"),
    ("different_entry", "UNVERIFIABLE_PROVENANCE"),
    ("different_quantity", "UNVERIFIABLE_PROVENANCE"),
    ("wrong_source_status", "UNVERIFIABLE_PROVENANCE"),
    ("blocked_signal", "UNVERIFIABLE_PROVENANCE"),
    ("contradictory_signal_status", "UNVERIFIABLE_PROVENANCE"),
    ("mismatched_lifecycle", "UNVERIFIABLE_PROVENANCE"),
    ("fictitious_ready", "UNVERIFIABLE_PROVENANCE"),
    ("invented_limit", "UNVERIFIABLE_PROVENANCE"),
    ("nan_price", "UNVERIFIABLE_PROVENANCE"),
    ("missing_stop", "INCOMPLETE_PLAN"),
    ("missing_target", "INCOMPLETE_PLAN"),
    ("missing_approval", "INCOMPLETE_PLAN"),
    ("missing_status", "INCOMPLETE_PLAN"),
    ("bool_quantity", "INCOMPLETE_PLAN"),
    ("non_boolean_approval", "INCOMPLETE_PLAN"),
    ("bool_price", "INCOMPLETE_PLAN"),
    ("bool_limit", "INCOMPLETE_PLAN"),
    ("legacy_plan", "INCOMPLETE_PLAN"),
])
def test_incomplete_or_unlinked_plans_are_not_promoted(stored_analysis, monkeypatch, damage, reason):
    store, analysis = stored_analysis
    plan = analysis["prepared_order_v2"]
    if damage == "missing_plan":
        del analysis["prepared_order_v2"]
    elif damage == "missing_signal":
        del analysis["signal_v2"]
    elif damage == "missing_timestamp":
        analysis["analyzed_at"] = None
    elif damage == "naive_timestamp":
        analysis["analyzed_at"] = datetime(2026, 9, 10)
    elif damage == "invalid_timestamp":
        analysis["analyzed_at"] = "unknown"
    elif damage == "wrong_symbol":
        plan["symbol"] = "NQ"
    elif damage == "wrong_timeframe":
        analysis["signal_v2"]["timeframe"] = "1H"
    elif damage == "wrong_direction":
        plan["side"] = "BUY"
    elif damage == "different_entry":
        plan["entry_price"] = 23500
    elif damage == "different_quantity":
        plan["quantity"] = 2
    elif damage == "wrong_source_status":
        plan["source_signal_status"] = "other-signal"
    elif damage == "blocked_signal":
        analysis["signal_v2"]["approved"] = False
    elif damage == "contradictory_signal_status":
        analysis["signal_v2"]["status"] = plan["source_signal_status"] = "BLOCKED"
    elif damage == "mismatched_lifecycle":
        analysis["trade_lifecycle_v2"] = {"prepared_order": {**plan, "quantity": 2}}
    elif damage == "fictitious_ready":
        plan["status"] = "READY"
    elif damage == "invented_limit":
        plan["order_type"] = "LIMIT"  # Missing the producer's corresponding limit price.
    elif damage == "nan_price":
        plan["entry_price"] = float("nan")
    elif damage in ("missing_stop", "missing_target", "missing_approval", "missing_status"):
        del plan[{"missing_stop": "stop_loss", "missing_target": "take_profit",
                  "missing_approval": "approved", "missing_status": "status"}[damage]]
    elif damage == "bool_quantity":
        plan["quantity"] = True
    elif damage == "non_boolean_approval":
        plan["approved"] = "true"
    elif damage == "bool_price":
        plan["entry_price"] = True
    elif damage == "bool_limit":
        plan["limit_price"] = True
    elif damage == "legacy_plan":
        # An old unlinked dataclass is not made trustworthy by being stored.
        analysis["prepared_order_v2"] = ExecutionPlan(
            "READY", "NQ", "BUY", "LIMIT", 1, 23500, 23450, 23650, 500, ["approved"],
        )
    store.save(analysis)
    before = deepcopy(store._storage)
    app = FastAPI()
    app.state.live_analysis_store = store
    app.include_router(router)
    client = TestClient(app)
    guards = forbid_plan_generation(monkeypatch, store)
    try:
        response = client.get(URL)
        assert response.status_code == 200
        assert_unavailable(response.json(), reason)
    finally:
        client.close()
    # NaN does not equal itself; compare its stable representation instead.
    assert repr(store._storage) == repr(before)
    for guard in guards:
        guard.assert_not_called()


def test_serialization_is_detached_and_preserves_real_limit_order(stored_analysis):
    store, _ = stored_analysis
    analysis = produce_analysis(
        ExecutionManagerV2(execution_mode="PAPER", maximum_contracts=3), order_type="LIMIT",
    )
    store.save(analysis)
    before = deepcopy(store._storage)
    payload = project_execution_manager(store=store)
    assert_existing_plan(payload, analysis)
    payload["prepared_order"]["warnings"].append("caller mutation")
    payload["source"]["signal"]["approved"] = False
    assert store._storage == before


def test_preexisting_lifecycle_risk_reduction_is_preserved(stored_analysis):
    store, analysis = stored_analysis
    analysis["signal_v2"]["contracts"] = 2
    analysis["trade_lifecycle_v2"] = {
        "prepared_order": deepcopy(analysis["prepared_order_v2"]),
        "risk_evaluation": {"approved": True, "contracts": 1},
    }
    store.save(analysis)
    assert_existing_plan(project_execution_manager(store=store), analysis)


def test_multiple_markets_require_explicit_selection_without_guessing(stored_analysis, monkeypatch):
    store, analysis = stored_analysis
    store.save(analysis)
    another = produce_analysis(ExecutionManagerV2(execution_mode="PAPER", maximum_contracts=3), symbol="MNQ")
    store.save(another)
    app = FastAPI()
    app.state.live_analysis_store = store
    app.include_router(router)
    client = TestClient(app)
    guards = forbid_plan_generation(monkeypatch, store)
    before = deepcopy(store._storage)
    try:
        assert_unavailable(client.get(URL).json(), "AMBIGUOUS_SOURCE")
        assert_unavailable(client.get(URL, params={"symbol": "MES"}).json(), "INCOMPLETE_SELECTION")
        assert_unavailable(client.get(URL, params={"symbol": "NQ", "timeframe": "5m"}).json(), "NO_DATA")
        for record in (analysis, another):
            response = client.get(URL, params={"symbol": record["symbol"], "timeframe": "5m"})
            assert response.status_code == 200
            assert_existing_plan(response.json(), record)
    finally:
        client.close()
    assert store._storage == before
    for guard in guards:
        guard.assert_not_called()


def test_missing_store_does_not_create_one():
    app = FastAPI()
    app.include_router(router)
    before = deepcopy(app.state._state)
    with TestClient(app) as client:
        assert_unavailable(client.get(URL).json(), "NO_DATA")
    assert app.state._state == before


def test_corrupt_store_key_is_unavailable_without_cleanup(stored_analysis):
    store, analysis = stored_analysis
    store._storage["invalid-key"] = analysis
    before = deepcopy(store._storage)
    assert_unavailable(project_execution_manager(store=store), "UNVERIFIABLE_PROVENANCE")
    assert store._storage == before
