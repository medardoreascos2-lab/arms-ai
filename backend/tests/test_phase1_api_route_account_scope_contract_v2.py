"""PH1-REQ-009: complete route inventory and account publication contracts."""
import inspect
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api.admin_authorization_dependency_v2 import ADMIN_TOKEN_HEADER
from backend.tests.phase1_api_route_inventory_v2 import (
    certificate, describe, key, load_manifest, routes,
)
from backend.tests.test_account_runtime_transition_v2 import hosted, target, trade


ADMIN_TOKEN = "phase1-route-scope-test-admin"


@pytest.fixture
def application(runtime, monkeypatch, tmp_path):
    # POLICY and the isolated PAPER account are installed before importing app.
    monkeypatch.setenv("ARMS_ADMIN_TOKEN", ADMIN_TOKEN)
    from backend.api.app import create_app

    return create_app(
        risk_event_store_path_v2=tmp_path / "risk-events.json",
    )


@pytest.mark.parametrize("path", ["/market/analyze", "/api/v2/backtesting/run"])
@pytest.mark.parametrize("credential", [None, "wrong-token", ADMIN_TOKEN])
def test_analysis_and_backtest_commands_require_admin_before_owner_call(
    application, monkeypatch, path, credential,
):
    from backend.services.live_market_analysis_service import LiveMarketAnalysisService

    if path == "/market/analyze":
        owner_call = Mock(return_value={"test_owner_reached": True})
        monkeypatch.setattr(LiveMarketAnalysisService, "analyze", owner_call)
        payload = {
            "symbol": "NQ", "timeframe": "5m", "candle_limit": 60,
            "account_balance": 50000, "risk_percent": .25,
            "point_value": 2, "reward_risk_ratio": 2,
        }
    else:
        owner_call = Mock(return_value=SimpleNamespace(to_dict=lambda: {"test_owner_reached": True}))
        monkeypatch.setattr(application.state.backtesting_orchestrator_v2, "run", owner_call)
        payload = {"candles": [{
            "symbol": "NQ", "timeframe": "5m", "open": 100, "high": 101,
            "low": 99, "close": 100, "volume": 10,
            "timestamp": "2026-01-02T15:00:00Z",
        }], "output_directory": "test-only-unused-output"}
    headers = {} if credential is None else {ADMIN_TOKEN_HEADER: credential}
    with TestClient(application) as client:
        response = client.post(path, json=payload, headers=headers)
    if credential == ADMIN_TOKEN:
        assert response.status_code == 200, response.text
        owner_call.assert_called_once()
    else:
        assert response.status_code == 401, response.text
        owner_call.assert_not_called()


def test_route_manifest_exhaustively_matches_registered_application(application):
    manifest = load_manifest()
    expected = {(row["path"], tuple(row["methods"])): row for row in manifest["routes"]}
    actual = routes(application)
    assert len(actual) == len({key(route) for route in actual}), "Duplicate registration"
    assert {key(route) for route in actual} == set(expected), "Unreviewed/missing API route"
    assert set(application.openapi()["paths"]) == {
        route.path for route in actual if getattr(route, "include_in_schema", False)
    }, "Inventory must use effective registered paths"
    for route in actual:
        recorded = expected[key(route)]
        evidence = describe(route, application)
        assert evidence == {field: recorded[field] for field in evidence}, key(route)
        assert recorded["owner"] and recorded["scope_resolution"] and recorded["authorization_rationale"]
        assert recorded["classification"] in {
            "GLOBAL_OBSERVATIONAL", "ACCOUNT_OBSERVATIONAL", "ACCOUNT_MUTATION",
            "CONTROL_PLANE_ADMIN", "EXECUTION_BOUNDARY", "WEBSOCKET_OBSERVATIONAL", "OTHER_JUSTIFIED",
        }
        if recorded["authorization"] == "ADMIN" and recorded["transport"] == "HTTP":
            assert evidence["canonical_admin_dependency"], key(route)
        if recorded["mutation"] == "NONE":
            forbidden = {"submit_order", "submit_signal", "open_position", "close_position",
                         "create_protection", "create_group", "record_open_trade", "update_position"}
            assert not {call.rsplit(".", 1)[-1] for call in evidence.get("calls", [])} & forbidden
    assert certificate(manifest["routes"]) == manifest["certificate"]
    assert manifest["certificate"]["UNCLASSIFIED_ROUTES"] == 0


@pytest.mark.parametrize("credential", [None, "wrong-token", "unconfigured"])
def test_every_admin_http_route_rejects_before_dispatch(application, monkeypatch, credential):
    from backend.tests.test_dashboard_read_execution_safety_v2 import capture, forbid_mutations

    before = capture(application)
    guards = forbid_mutations(application, monkeypatch)
    if credential == "unconfigured":
        monkeypatch.setattr(application.state, "admin_authorization_v2", None)
    headers = {} if credential is None else {ADMIN_TOKEN_HEADER: credential}
    client = TestClient(application)
    try:
        for row in load_manifest()["routes"]:
            if row["authorization"] != "ADMIN" or row["transport"] != "HTTP":
                continue
            path = row["path"].replace("{position_id}", "missing").replace("{job_id}", "missing")
            response = client.request(row["methods"][0], path, json={}, headers=headers)
            assert response.status_code == (503 if credential == "unconfigured" else 401), (path, response.text)
        assert capture(application) == before
        for guard in guards:
            guard.assert_not_called()
    finally:
        client.close()


def _read_path(row):
    path = row["path"].replace("{strategy_id}", "missing").replace("{job_id}", "missing")
    return path, {"symbol": "MNQ", "timeframe": "5m", "starting_balance": 50000,
                  "date": "2026-01-02", "regime": "TRENDING", "volatility": "NORMAL"}


def test_every_account_route_binds_to_new_publication(hosted):
    source = hosted.c.published
    source_routes = {key(route): route for route in routes(source.application)}
    response = hosted.client.post(
        "/api/v2/dashboard/account-manager/switch", json=target(hosted, "B"),
    )
    assert response.status_code == 200, response.text
    current = hosted.c.published
    current_routes = {key(route): route for route in routes(current.application)}
    assert set(current_routes) == set(source_routes)
    assert current.runtime is not source.runtime
    assert current.application.state.trade_lifecycle_service_v2 is current.runtime.trade_lifecycle_service
    assert current.application.state.account_switch_safety_v2 is hosted.c
    assert current.application.state.trade_journal_v2 is current.runtime.trade_lifecycle_service.trade_journal_v2
    assert current.application.state.portfolio_manager_v2 is current.runtime.portfolio_manager_v2
    assert current.application.state.account_state_manager_v2 is current.runtime.account_state_manager_v2
    for row in load_manifest()["routes"]:
        if row["account_scope"] not in {"ACTIVE_RUNTIME", "EXPLICIT_ACCOUNT"}:
            continue
        route_key = (row["path"], tuple(row["methods"]))
        new = inspect.getclosurevars(current_routes[route_key].endpoint).nonlocals
        old = inspect.getclosurevars(source_routes[route_key].endpoint).nonlocals
        for name, owner in new.items():
            if owner is not None:
                assert owner is not old[name], (route_key, name)
                for binding in row["closure_owners"][name]["state_bindings"]:
                    assert getattr(current.application.state, binding) is owner
        for field in row["state_fields"]:
            assert hasattr(current.application.state, field), (route_key, field)
            value = getattr(current.application.state, field)
            if value is not None and not isinstance(value, (str, int, float, bool)) and value is not hosted.c:
                assert value is not getattr(source.application.state, field), (route_key, field)


@pytest.mark.parametrize("unavailable", ["switching", "failed"])
def test_every_account_http_route_fails_closed_when_runtime_unavailable(hosted, monkeypatch, unavailable):
    monkeypatch.setattr(hosted.c, unavailable, True)
    for row in load_manifest()["routes"]:
        if row["transport"] != "HTTP" or row["account_scope"] not in {"ACTIVE_RUNTIME", "EXPLICIT_ACCOUNT"}:
            continue
        path, params = _read_path(row)
        response = hosted.client.request(row["methods"][0], path, params=params, json={})
        assert response.status_code == 409, (path, response.text)
        assert response.json()["reason"] == "account_runtime_unavailable"
    monkeypatch.setattr(hosted.c, unavailable, False)


def test_all_account_reads_after_switch_are_observational(hosted, monkeypatch):
    from backend.tests.test_dashboard_read_execution_safety_v2 import capture, forbid_mutations

    response = hosted.client.post(
        "/api/v2/dashboard/account-manager/switch", json=target(hosted, "B"),
    )
    assert response.status_code == 200
    app = hosted.c.published.application
    generation = hosted.c.published.generation

    @app.middleware("http")
    async def record_selected_application(request, call_next):
        assert request.app is app
        response = await call_next(request)
        response.headers["X-Test-Generation"] = str(generation)
        return response

    before = capture(app)
    guards = forbid_mutations(app, monkeypatch)
    for row in load_manifest()["routes"]:
        if row["classification"] != "ACCOUNT_OBSERVATIONAL":
            continue
        path, params = _read_path(row)
        response = hosted.client.get(path, params=params)
        assert response.status_code in {200, 404, 503}, (path, response.text)
        assert response.headers["X-Test-Generation"] == str(generation)
        if path == "/market/open-position":
            assert response.status_code == 503
            assert response.json()["detail"] == "legacy_position_manager_unavailable"
    assert capture(app) == before
    for guard in guards:
        guard.assert_not_called()


@pytest.mark.parametrize("path", ["/market/analyze", "/market/webhook"])
def test_incompatible_legacy_market_commands_fail_before_state_changes(hosted, monkeypatch, path):
    from backend.tests.test_dashboard_read_execution_safety_v2 import capture, forbid_mutations

    app = hosted.c.published.application
    before = capture(app)
    guards = forbid_mutations(app, monkeypatch)
    add = Mock(wraps=app.state.live_candle_store.add)
    monkeypatch.setattr(app.state.live_candle_store, "add", add)
    if path == "/market/analyze":
        payload = {"symbol": "NQ", "timeframe": "5m", "candle_limit": 60,
                   "account_balance": 50000, "risk_percent": .25,
                   "point_value": 2, "reward_risk_ratio": 2}
    else:
        payload = {"symbol": "NQ", "timeframe": "5m", "open": 100,
                   "high": 101, "low": 99, "close": 100, "volume": 10,
                   "timestamp": "2026-01-02T15:00:00Z"}
    response = hosted.client.post(
        path, json=payload, headers={"X-ARMS-TOKEN": app.state.webhook_token},
    )
    assert response.status_code == 503, response.text
    assert response.json()["detail"] == "legacy_position_manager_unavailable"
    add.assert_not_called()
    assert capture(app) == before
    for guard in guards:
        guard.assert_not_called()


def test_account_switch_isolates_actual_journal_jobs_and_market_store(hosted):
    trade(hosted, close_price=10010.0)
    source = hosted.c.published
    state = source.application.state
    job = state.backtesting_job_manager_v2.create_job(job_id="source-account-only")
    state.live_analysis_store.save({
        "symbol": "MNQ", "timeframe": "5m", "current_price": 10010,
        "trend": "TEST_A", "decision": "OBSERVE", "probability": 0,
        "risk": {}, "analyzed_at": "2026-01-02T15:00:00Z",
    })
    journal_path = "/api/v3/dashboard/journal-debug"
    journal = hosted.client.get(journal_path).json()
    assert journal["total"] == 1
    params = {"symbol": "MNQ", "timeframe": "5m"}
    assert hosted.client.get("/market/latest-analysis", params=params).json()["trend"] == "TEST_A"
    assert hosted.client.get(f"/api/v2/backtesting/jobs/{job.job_id}").status_code == 200
    assert hosted.client.post(
        "/api/v2/dashboard/account-manager/switch", json=target(hosted, "B"),
    ).status_code == 200
    assert hosted.client.get(journal_path).json()["total"] == 0
    assert hosted.client.get("/market/latest-analysis", params=params).status_code == 404
    assert hosted.client.get(f"/api/v2/backtesting/jobs/{job.job_id}").status_code == 404
    assert hosted.client.delete(f"/api/v2/backtesting/jobs/{job.job_id}").status_code == 404
    assert state.backtesting_job_manager_v2.get_job(job.job_id) is job
    assert hosted.client.post(
        "/api/v2/dashboard/account-manager/switch", json=target(hosted, "A"),
    ).status_code == 200
    assert hosted.client.get(journal_path).json() == journal
    # Volatile market/backtest stores are reconstructed, not persisted or
    # silently rebound to an old-generation application when switching back.
    assert hosted.client.get("/market/latest-analysis", params=params).status_code == 404
    assert hosted.client.get(f"/api/v2/backtesting/jobs/{job.job_id}").status_code == 404
