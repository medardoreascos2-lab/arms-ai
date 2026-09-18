from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.api.admin_authorization_dependency_v2 import ADMIN_TOKEN_HEADER
from backend.security.admin_authorization_v2 import AdminAuthorizationV2

PATH = "/api/v2/dashboard/ws"
TOKEN = "phase1-websocket-admin-token"


@pytest.fixture
def client(runtime, monkeypatch, tmp_path):
    # The shared runtime fixture supplies every required API policy setting
    # with monkeypatch and an isolated PAPER account before app import.
    monkeypatch.setenv("ARMS_ADMIN_TOKEN", TOKEN)
    from backend.api.app import create_app

    application = create_app(
        runtime_context=runtime.context,
        risk_event_store_path_v2=tmp_path / "websocket-risk-events.json",
    )
    # Reuse the existing no-trade probes only after the isolated app import.
    from backend.tests.test_dashboard_read_execution_safety_v2 import (
        capture,
        forbid_mutations,
    )

    before = capture(application)
    guards = forbid_mutations(application, monkeypatch)
    client = TestClient(application)
    try:
        yield client
    finally:
        client.close()
        assert capture(application) == before
        for guard in guards:
            guard.assert_not_called()


@pytest.fixture
def projection(client, monkeypatch):
    state = client.app.state
    snapshot = Mock(wraps=state.dashboard_live_data_service_v2.get_snapshot)
    connect = AsyncMock(wraps=state.dashboard_websocket_hub_v2.connect)
    monkeypatch.setattr(state.dashboard_live_data_service_v2, "get_snapshot", snapshot)
    monkeypatch.setattr(state.dashboard_websocket_hub_v2, "connect", connect)
    return snapshot, connect


def _connect(client, *, headers=None):
    return client.websocket_connect(
        PATH,
        headers=headers or {},
    )


def test_dashboard_websocket_rejects_missing_admin_token(client, projection):
    with pytest.raises(WebSocketDisconnect) as error:
        with _connect(client):
            pytest.fail("Unauthorized WebSocket was accepted")
    assert error.value.code == 1008
    for probe in projection:
        probe.assert_not_called()


def test_dashboard_websocket_rejects_wrong_admin_token(client, projection):
    with pytest.raises(WebSocketDisconnect) as error:
        with _connect(
            client,
            headers={ADMIN_TOKEN_HEADER: "arms-dashboard-ws-test-admin-token"},
        ):
            pytest.fail("Unauthorized WebSocket was accepted")
    assert error.value.code == 1008
    for probe in projection:
        probe.assert_not_called()


def test_dashboard_websocket_accepts_valid_admin_token(client, projection, monkeypatch):
    authority = client.app.state.admin_authorization_v2
    assert isinstance(authority, AdminAuthorizationV2)
    authorize = Mock(wraps=authority.require_authorized)
    monkeypatch.setattr(authority, "require_authorized", authorize)
    with _connect(
        client,
        headers={ADMIN_TOKEN_HEADER: TOKEN},
    ) as websocket:
        payload = websocket.receive_json()

    assert payload["event_type"] == "dashboard_snapshot"
    authorize.assert_called_once_with(TOKEN)
    projection[0].assert_called_once_with()
    projection[1].assert_awaited_once()
    assert client.app.state.dashboard_websocket_hub_v2.get_connection_count() == 0


@pytest.mark.parametrize("authority", [None, object()], ids=["missing", "invalid"])
def test_dashboard_websocket_requires_canonical_authority(
    client, projection, monkeypatch, authority,
):
    monkeypatch.setattr(client.app.state, "admin_authorization_v2", authority)
    with pytest.raises(WebSocketDisconnect) as error:
        with _connect(client, headers={ADMIN_TOKEN_HEADER: TOKEN}):
            pytest.fail("WebSocket accepted without a canonical authority")
    assert error.value.code == 1008
    for probe in projection:
        probe.assert_not_called()


def test_dashboard_websocket_obeys_canonical_authority_rejection(
    client, projection, monkeypatch,
):
    reject = Mock(side_effect=PermissionError("injected canonical rejection"))
    monkeypatch.setattr(client.app.state.admin_authorization_v2, "require_authorized", reject)
    with pytest.raises(WebSocketDisconnect) as error:
        with _connect(client, headers={ADMIN_TOKEN_HEADER: TOKEN}):
            pytest.fail("WebSocket bypassed canonical authority rejection")
    assert error.value.code == 1008
    reject.assert_called_once_with(TOKEN)
    for probe in projection:
        probe.assert_not_called()
