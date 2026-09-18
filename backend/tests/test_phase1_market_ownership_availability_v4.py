"""Market ingress and projections use the published runtime's data owners."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api.admin_authorization_dependency_v2 import ADMIN_TOKEN_HEADER
from backend.tests.test_account_runtime_transition_v2 import hosted, switch
from backend.tests.test_dashboard_read_execution_safety_v2 import capture, forbid_mutations


PRICE_PATH = "/api/v3/dashboard/market-price"


@pytest.mark.parametrize("damage", ["stale", "future", "missing_timestamp", "missing_symbol", "manual_source"])
def test_price_ingress_cannot_bypass_canonical_freshness(hosted, monkeypatch, damage):
    app = hosted.c.published.application
    payload = {"symbol": "MNQ", "price": 10000., "timestamp": datetime.now(timezone.utc).isoformat()}
    if damage in {"stale", "future"}:
        payload["timestamp"] = (datetime.now(timezone.utc) + timedelta(
            seconds=-3600 if damage == "stale" else 3600,
        )).isoformat()
    elif damage == "missing_timestamp":
        payload.pop("timestamp")
    elif damage == "missing_symbol":
        payload.pop("symbol")
    else:
        payload["source"] = "MANUAL"
    before = capture(app)
    feed_before = app.state.price_feed_service_v2.get_state()
    monitor = Mock(return_value={})
    monkeypatch.setattr(app.state.live_position_monitor_v2, "process_price", monitor)
    response = hosted.client.post(PRICE_PATH, json=payload)
    assert response.status_code in {400, 422}, response.text
    monitor.assert_not_called()
    assert capture(app) == before
    assert app.state.price_feed_service_v2.get_state() == feed_before


def test_price_feed_unavailable_is_explicit_and_observational(hosted, monkeypatch):
    app = hosted.c.published.application
    before = capture(app)
    monkeypatch.setattr(app.state, "price_feed_service_v2", None)
    response = hosted.client.post(PRICE_PATH, json={
        "symbol": "MNQ", "price": 10000., "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    assert response.status_code == 503
    assert capture(app) == before


@pytest.mark.parametrize("path", ["/market/latest-analysis", "/market/latest-signal"])
@pytest.mark.parametrize("quote_state", ["missing", "stale", "fresh"])
def test_cached_market_reports_do_not_imply_current_quote_availability(hosted, monkeypatch, path, quote_state):
    from backend.tests.test_latest_market_analysis_router import build_analysis
    from backend.tests.test_latest_market_signal_router import build_signal

    app = hosted.c.published.application
    app.state.live_analysis_store.save(build_analysis())
    app.state.live_signal_store.save(build_signal())
    if quote_state != "missing":
        app.state.runtime_quote_authority_v2.publish_quote(
            symbol="NQ", bid=10000, ask=10000.25,
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=3600 if quote_state == "stale" else 1),
        )
    before = capture(app)
    guards = forbid_mutations(app, monkeypatch)
    response = hosted.client.get(path, params={"symbol": "NQ", "timeframe": "5m"})
    assert response.status_code == 200
    assert response.json()["market_data"]["status"] == ("AVAILABLE" if quote_state == "fresh" else "UNAVAILABLE")
    assert response.json()["market_data"]["snapshot_only"] is True
    assert capture(app) == before
    for guard in guards:
        guard.assert_not_called()


@pytest.mark.parametrize("price", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_price_rejected_before_feed_state_or_monitor(price):
    from backend.services.price_feed_service_v2 import PriceFeedServiceV2

    monitor = Mock()
    service = PriceFeedServiceV2(live_position_monitor_v2=monitor, maximum_age_seconds=30)
    before = service.get_state()
    with pytest.raises(ValueError):
        service.process_price(symbol="MNQ", current_price=price, source="MARKET_WEBHOOK", timestamp=datetime.now(timezone.utc))
    assert service.get_state() == before
    monitor.process_price.assert_not_called()


def test_legacy_webhook_cannot_settle_disconnected_positions(runtime, monkeypatch):
    from backend.api.app import create_app
    from backend.execution.position_manager import PositionManager
    from backend.tests.test_open_position_router import build_trade
    from backend.tests.test_market_webhook_router import build_payload

    manager = PositionManager()
    manager.open_position(build_trade())
    app = create_app(position_manager=manager)
    before = manager.get_open_position(symbol="NQ", timeframe="5m")
    payload = build_payload()
    payload.update(high=22000, low=21000, close=21600)
    with TestClient(app) as client:
        response = client.post("/market/webhook", json=payload, headers={"X-ARMS-TOKEN": app.state.webhook_token})
    assert response.status_code == 503, response.text
    assert manager.get_open_position(symbol="NQ", timeframe="5m") == before
    assert app.state.live_candle_store.count(symbol="NQ", timeframe="5m") == 0


@pytest.mark.parametrize("name", ["trade-setup", "execution-simulator", "intelligence-decision", "confidence-fusion"])
def test_fixed_market_examples_explicitly_disclose_unavailable_live_data(hosted, monkeypatch, name):
    app = hosted.c.published.application
    before = capture(app)
    guards = forbid_mutations(app, monkeypatch)
    response = hosted.client.get("/api/v2/dashboard/" + name)
    assert response.status_code == 200
    assert response.json()["market_data"] == {
        "status": "UNAVAILABLE", "source": "DEMONSTRATION", "snapshot_only": True,
    }
    assert capture(app) == before
    for guard in guards:
        guard.assert_not_called()


MANIFEST = Path(__file__).with_name("phase1_market_route_inventory_v4.json")


def test_every_market_registration_has_reviewed_owner_and_availability(hosted):
    from backend.tests.phase1_api_route_inventory_v2 import describe, routes

    inventory = json.loads(MANIFEST.read_text())
    app = hosted.c.published.application
    actual_rows = [describe(r, app) for r in routes(app)]
    actual = {(r["path"], tuple(r["methods"])): r for r in actual_rows}
    recorded = {(r["path"], tuple(r["methods"])): r for r in inventory["routes"]}
    # All registrations have a disposition, even non-market routes.
    assert len(actual) == len(actual_rows)
    assert set(actual) == set(recorded) | {
        (r["path"], tuple(r["methods"])) for r in inventory["non_market_dispositions"]
    }
    assert len(recorded) == inventory["certificate"]["TOTAL_MARKET_ROUTES"]
    assert inventory["certificate"]["UNCLASSIFIED_MARKET_ROUTES"] == 0
    for path, row in recorded.items():
        for field in ("methods", "endpoint", "module", "canonical_admin_dependency", "source_sha256", "calls", "state_fields"):
            assert actual[path][field] == row[field], (path, field)
        for field in ("authorization", "account_scope", "read_or_mutation", "market_data_owner", "source_of_truth", "freshness_policy", "unavailable_behavior", "legacy_or_canonical"):
            assert row[field], (path, field)
        if row["authorization"] == "ADMIN":
            assert actual[path]["canonical_admin_dependency"]
        if row["read_or_mutation"] == "OBSERVATIONAL":
            assert not {c.rsplit(".", 1)[-1] for c in row["calls"]} & {
                "submit_order", "submit_signal", "prepare_order", "open_position", "close_position", "evaluate_candle",
            }


def test_fresh_price_delegates_once_without_manufacturing_l1(hosted, monkeypatch):
    app = hosted.c.published.application
    monitor = Mock(return_value={"test_observation": True})
    monkeypatch.setattr(app.state.live_position_monitor_v2, "process_price", monitor)
    before = capture(app)
    response = hosted.client.post(PRICE_PATH, json={
        "symbol": "MNQ", "price": 10000, "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    assert response.status_code == 200, response.text
    assert response.json()["processed"] is True
    monitor.assert_called_once()
    assert app.state.price_feed_service_v2.get_state()["price_count"] == 1
    assert app.state.runtime_quote_authority_v2.get_quote(symbol="MNQ") is None
    assert capture(app) == before


def test_quote_ownership_does_not_leak_across_a_b_a_publications(hosted):
    owners = []
    for account in ("A", "B", "A"):
        if owners:
            assert switch(hosted, account).status_code == 200
        app = hosted.c.published.application
        owner = app.state.runtime_quote_authority_v2
        assert all(owner is not old for old in owners)
        assert owner.get_quote(symbol="NQ") is None
        assert app.state.price_feed_service_v2.get_state()["price_count"] == 0
        assert app.state.live_candle_store.count(symbol="NQ", timeframe="5m") == 0
        before = capture(app)
        response = hosted.client.post("/market/quote", headers={"X-ARMS-TOKEN": app.state.webhook_token}, json={
            "symbol": "NQ", "bid": 100 + len(owners), "ask": 101 + len(owners),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        assert response.status_code == 201, response.text
        assert owner.get_quote(symbol="NQ")["bid"] == 100 + len(owners)
        assert capture(app) == before
        owners.append(owner)
    assert [owner.get_quote(symbol="NQ")["bid"] for owner in owners] == [100, 101, 102]


@pytest.mark.parametrize("path", ["/market/quote", "/market/webhook", PRICE_PATH, "/market/analyze", "/api/v2/market-hours/refresh"])
@pytest.mark.parametrize("token", [None, "incorrect"])
def test_market_mutations_reject_unauthorized_before_any_owner(hosted, monkeypatch, path, token):
    from backend.tests.test_market_webhook_router import build_payload
    app = hosted.c.published.application
    before = capture(app)
    feed_before = app.state.price_feed_service_v2.get_state()
    guards = forbid_mutations(app, monkeypatch)
    guard = Mock(side_effect=AssertionError("Unauthorized market write"))
    monkeypatch.setattr(app.state.runtime_quote_authority_v2, "publish_quote", guard)
    monkeypatch.setattr(app.state.price_feed_service_v2, "process_price", guard)
    monkeypatch.setattr(app.state.live_candle_store, "add", guard)
    header = "X-ARMS-TOKEN" if path in {"/market/quote", "/market/webhook"} else ADMIN_TOKEN_HEADER
    # A separate client avoids inheriting the hosted fixture's authorized headers.
    with TestClient(app) as client:
        response = client.post(path, headers={} if token is None else {header: token}, json={
            **build_payload(), "bid": 100, "ask": 101, "price": 100,
            "file_path": "unused", "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    assert response.status_code == 401, response.text
    assert capture(app) == before
    assert app.state.price_feed_service_v2.get_state() == feed_before
    guard.assert_not_called()
    for mutation in guards:
        mutation.assert_not_called()


@pytest.mark.parametrize("path", ["/market/latest-analysis", "/market/latest-signal"])
def test_unknown_market_snapshot_is_missing_not_a_fallback(hosted, path):
    app = hosted.c.published.application
    before = capture(app)
    response = hosted.client.get(path, params={"symbol": "UNSUPPORTED", "timeframe": "5m"})
    assert response.status_code == 404
    assert app.state.runtime_quote_authority_v2.get_quote(symbol="UNSUPPORTED") is None
    assert capture(app) == before


def test_generic_quote_storage_does_not_grant_instrument_support(hosted):
    from backend.instruments.instrument_profile_engine import InstrumentProfileEngine
    app = hosted.c.published.application
    before = capture(app)
    response = hosted.client.post("/market/quote", headers={"X-ARMS-TOKEN": app.state.webhook_token}, json={
        "symbol": "UNSUPPORTED", "bid": 10, "ask": 11, "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    assert response.status_code == 201
    assert app.state.runtime_quote_authority_v2.get_quote(symbol="UNSUPPORTED")["bid"] == 10
    assert app.state.runtime_quote_authority_v2.get_quote(symbol="NQ") is None
    with pytest.raises(ValueError):
        InstrumentProfileEngine().get_profile(symbol="UNSUPPORTED")
    assert capture(app) == before


@pytest.mark.parametrize("provider_state", ["missing", "error"])
def test_external_provider_failure_never_manufactures_price_or_calls_monitor(provider_state):
    from backend.services.price_feed_service_v2 import PriceFeedServiceV2
    provider = None if provider_state == "missing" else Mock(provider_name="BROKER")
    if provider is not None:
        provider.get_quote.side_effect = RuntimeError("provider offline")
    monitor = Mock()
    feed = PriceFeedServiceV2(live_position_monitor_v2=monitor, maximum_age_seconds=30,
                              external_market_data_provider_v2=provider)
    before = feed.get_state()
    with pytest.raises(RuntimeError):
        feed.pull_external_quote(symbol="NQ", timeframe="5m")
    assert feed.get_state() == before
    monitor.process_price.assert_not_called()
