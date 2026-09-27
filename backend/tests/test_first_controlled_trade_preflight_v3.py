"""Preflight GET cannot authorize, reconcile, ingest, or publish an operation."""
from copy import deepcopy
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.sim_native_financial_api_v3 import create_sim_native_financial_router_v3
from backend.services.sim_native_financial_runtime_service_v3 import SimNativeFinancialRuntimeServiceV3
from backend.tests.test_sim_native_admission_runtime_evidence_v3 import evidence_environment, environment, disk


def test_unstarted_owner_reports_unknown_facts_without_side_effects():
    svc = SimNativeFinancialRuntimeServiceV3()
    result = svc.get_first_trade_preflight()
    assert result["status"] == "NOT_READY" and result["authorization_state"] == "NOT_AUTHORIZED"
    assert result["native_submit_enabled"] is None and result["controlled_observation_only"] is None
    assert result["open_position_count"] is None and svc._runtime is None


@pytest.fixture
def owner(evidence_environment):
    env = evidence_environment
    svc = SimNativeFinancialRuntimeServiceV3(clock=lambda: env.now)
    svc.start()
    assert svc.get_snapshot()["status"] == "NO_OPERATION"
    try:
        yield env, svc
    finally:
        svc.stop()


def test_ready_is_not_authorization_and_gets_cannot_mutate(owner, monkeypatch):
    env, svc = owner
    denied = Mock(side_effect=AssertionError("GET must not execute or reconcile"))
    for obj, name in ((svc, "observe"), (svc._integration, "reconcile"), (svc._integration, "publish_admitted"),
                      (svc._runtime.lifecycle, "submit_signal"),
                      (svc._runtime.lifecycle.native_admission_producer_v3, "produce")):
        monkeypatch.setattr(obj, name, denied)
    app = FastAPI()
    app.include_router(create_sim_native_financial_router_v3(svc.get_snapshot, svc.get_first_trade_preflight))
    client = TestClient(app)
    before = disk(env.root)
    finance = svc.get_snapshot()
    url = "/api/v3/dashboard/sim-native-first-trade-preflight"
    for _ in range(3):
        response = client.get(url, params={"account": "Live", "instrument": "ES", "runtime_generation": "99"})
        value = response.json()
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert value["status"] == "READY_FOR_AUTHORIZATION", value
        assert value["authorization_state"] == "NOT_AUTHORIZED"
        assert value["quantity_limit"] == 1
        assert value["native_account"] == "Sim101" and value["instrument"] == "NQ DEC26"
        assert value["native_submit_enabled"] is value["auto_retry_allowed"] is False
        assert value["controlled_observation_only"] is True
        assert "runtime_ref" not in value and "evidence" not in value
    for verb in (client.post, client.put, client.delete):
        assert verb(url).status_code == 405
    assert disk(env.root) == before and svc.get_snapshot() == finance
    denied.assert_not_called()


@pytest.mark.parametrize("field,value", [("status", "OPEN"), ("status", "CLOSED"), ("status", "AWAITING_EXECUTION"),
    ("status", "UNAVAILABLE"), ("open_position_count", 1), ("closed_position_count", 1), ("journal_count", 1),
    ("pending_dashboard_events", 1), ("open_position_count", False), ("journal_count", None),
    ("backend_account_id", "PAPER"), ("instrument", "ES"), ("native_account", "Sim102"),
    ("provider", "Live"), ("runtime_generation", 2), ("runtime_generation", True)])
def test_financial_uncertainty_cannot_be_ready_or_cleared(owner, field, value):
    env, svc = owner
    svc._view[field] = value
    before = disk(env.root); original = deepcopy(svc._view)
    result = svc.get_first_trade_preflight()
    assert result["status"] == "NOT_READY" and result["reason"] == "FINANCIAL_NOT_QUIESCENT"
    assert svc._view == original and disk(env.root) == before


def test_session_closed_preflight_is_not_ready(owner):
    env, svc = owner
    env.snapshot["physical_test_readiness"] = "MARKET_SESSION_CLOSED"; env.write()
    before = disk(env.root)
    value = svc.get_first_trade_preflight()
    assert value["status"] == "NOT_READY" and value["reason"] == "NOT_READY_SESSION_CLOSED"
    assert value["financial_status"] == "NO_OPERATION" and value["heartbeat_fresh"] is True
    assert disk(env.root) == before


def test_production_mount_is_read_only_and_has_no_paper_credential(owner, tmp_path, monkeypatch):
    from backend.api.asgi import create_asgi_app
    env, svc = owner
    config = tmp_path / "paper.json"
    config.write_text('{"active_account":"TOPSTEP_150K"}')
    app = create_asgi_app(account_config_path=config, state_path=tmp_path / "paper/state.json",
                          sim_native_service_factory=lambda: svc)
    with TestClient(app) as client:
        denied = Mock(side_effect=AssertionError("no execution from GET"))
        monkeypatch.setattr(svc._runtime.lifecycle, "submit_signal", denied)
        url = "/api/v3/dashboard/sim-native-first-trade-preflight"
        before = disk(env.root)
        assert client.get(url).json()["status"] == "READY_FOR_AUTHORIZATION"
        assert client.post(url).status_code == 405
        assert disk(env.root) == before
        denied.assert_not_called()
