from __future__ import annotations

import asyncio
import inspect
from threading import RLock
from types import SimpleNamespace

import pytest
from fastapi.routing import APIWebSocketRoute

from backend.api.account_runtime_application_v2 import AccountRuntimeApplicationV2
from backend.api.admin_authorization_dependency_v2 import ADMIN_TOKEN_HEADER
from backend.api.dashboard_websocket_api_v2 import (
    create_dashboard_websocket_router_v2,
)
from backend.tests.test_account_runtime_transition_v2 import (
    ADMIN_TOKEN,
    hosted,
    target,
)


WEBSOCKET_PATH = "/api/v2/dashboard/ws"


class _Hub:
    async def connect(self, *, websocket):
        return None

    def disconnect(self, *, websocket):
        return None


class _Live:
    def get_snapshot(self):
        return {
            "dashboard_status": "READY",
        }


def _router():
    return create_dashboard_websocket_router_v2(
        websocket_hub_v2=_Hub(),
        live_data_service_v2=_Live(),
    )


def _websocket_routes():
    router = _router()

    return [
        route
        for route in router.routes
        if isinstance(route, APIWebSocketRoute)
        and route.path == WEBSOCKET_PATH
    ]


def _route():
    routes = _websocket_routes()

    assert len(routes) == 1, (
        "The dashboard WebSocket factory must expose exactly "
        f"one {WEBSOCKET_PATH!r} route; found {len(routes)}"
    )

    return routes[0]


def _dependency_names(route):
    names = set()

    def visit(node):
        call = getattr(node, "call", None)

        if call is not None:
            names.add(
                getattr(
                    call,
                    "__name__",
                    call.__class__.__name__,
                )
            )

        for child in (
            getattr(node, "dependencies", ()) or ()
        ):
            visit(child)

    visit(route.dependant)

    return names


def test_dashboard_websocket_factory_registers_route_exactly_once():
    route = _route()

    assert isinstance(route, APIWebSocketRoute)
    assert route.path == WEBSOCKET_PATH


def test_dashboard_websocket_is_observational_not_http_mutation():
    route = _route()

    assert not getattr(route, "methods", None)


def test_dashboard_websocket_exposes_no_execution_submission_owner():
    route = _route()

    source = inspect.getsource(route.endpoint).lower()

    forbidden = (
        "submit_order",
        "submit_signal",
        "execute_order",
        "paper_execution_engine",
        "open_position",
        "close_position",
        "create_protection",
        "create_group",
    )

    found = [
        token
        for token in forbidden
        if token in source
    ]

    assert found == [], (
        "Dashboard WebSocket endpoint appears to own execution "
        f"mutation behavior: {found!r}"
    )


def test_dashboard_websocket_uses_snapshot_projection():
    route = _route()

    source = inspect.getsource(route.endpoint)

    assert "get_snapshot" in source
    assert "send_json" in source


def test_dashboard_websocket_uses_imperative_canonical_authorization():
    route = _route()

    dependencies = {
        name.lower().replace("-", "_")
        for name in _dependency_names(route)
    }

    known_admin_dependencies = {
        "require_admin_authorization_v2",
        "require_admin_authorization",
        "admin_authorization",
        "admin_authorization_dependency",
    }

    authorization_present = bool(
        dependencies & known_admin_dependencies
    )

    # FastAPI Depends is absent because this endpoint invokes the canonical
    # authority itself. Behavioral authorization is certified in the contract.
    assert authorization_present is False
    source = inspect.getsource(route.endpoint)
    assert "AdminAuthorizationV2" in source
    assert "authority.require_authorized" in source
    assert "ADMIN_TOKEN_HEADER" in source


def test_account_runtime_application_has_websocket_retirement_guards():
    import backend.api.account_runtime_application_v2 as module

    source = inspect.getsource(
        module.AccountRuntimeApplicationV2.__call__
    )

    required = (
        'scope["type"] == "websocket"',
        '"websocket.close"',
        "coordinator._published is bundle",
        "Retired account socket",
    )

    missing = [
        token
        for token in required
        if token not in source
    ]

    assert missing == [], (
        "Account runtime application is missing expected "
        f"WebSocket retirement evidence: {missing!r}"
    )


def test_account_runtime_application_closes_stale_generation_socket():
    import backend.api.account_runtime_application_v2 as module

    source = inspect.getsource(
        module.AccountRuntimeApplicationV2.__call__
    )

    assert '"code": 1012' in source
    assert "coordinator._published is not bundle" in source


def test_account_runtime_application_fails_closed_during_switch():
    import backend.api.account_runtime_application_v2 as module

    source = inspect.getsource(
        module.AccountRuntimeApplicationV2.__call__
    )

    assert "coordinator.switching" in source
    assert "coordinator.failed" in source
    assert '"code": 1013' in source


@pytest.mark.parametrize("unavailable", ["switching", "failed", "unpublished", "busy"])
def test_unavailable_account_rejects_socket_before_dispatch(unavailable):
    async def exercise():
        dispatched = []

        async def application(scope, receive, send):
            dispatched.append(scope)

        bundle = SimpleNamespace(application=application)
        coordinator = SimpleNamespace(
            switching=unavailable == "switching",
            failed=unavailable == "failed",
            _published=None if unavailable == "unpublished" else bundle,
            published=bundle,
            lock=RLock(),
        )
        if unavailable == "busy":
            # A primitive lock stays unavailable even to its acquiring thread.
            from threading import Lock

            coordinator.lock = Lock()
            coordinator.lock.acquire()
        sent = []

        async def send(message):
            sent.append(message)

        async def receive():
            pytest.fail("Unavailable runtime must not consume WebSocket input")

        try:
            await AccountRuntimeApplicationV2(coordinator)(
                {"type": "websocket", "path": WEBSOCKET_PATH}, receive, send,
            )
        finally:
            if unavailable == "busy":
                coordinator.lock.release()
        assert dispatched == []
        assert sent == [{"type": "websocket.close", "code": 1013}]

    asyncio.run(exercise())


@pytest.mark.parametrize("retirement", ["new_generation", "failed"])
def test_retired_socket_closes_and_rejects_further_projection(retirement):
    async def exercise():
        messages = asyncio.Queue()
        account_sends = []
        stopped = asyncio.Event()

        async def application(scope, receive, send):
            account_sends.append(send)
            try:
                await send({"type": "websocket.accept"})
                await send({"type": "websocket.send", "text": "account A generation 1"})
                await asyncio.Event().wait()
            finally:
                stopped.set()

        bundle = SimpleNamespace(application=application)
        coordinator = SimpleNamespace(
            switching=False, failed=False, _published=bundle, published=bundle,
            lock=RLock(),
        )

        async def receive():
            return {"type": "websocket.connect"}

        worker = asyncio.create_task(AccountRuntimeApplicationV2(coordinator)(
            {"type": "websocket", "path": WEBSOCKET_PATH}, receive, messages.put,
        ))
        try:
            assert await asyncio.wait_for(messages.get(), 2) == {"type": "websocket.accept"}
            assert (await asyncio.wait_for(messages.get(), 2))["text"] == "account A generation 1"
            if retirement == "new_generation":
                coordinator._published = SimpleNamespace(application=application)
            else:
                coordinator.failed = True
            assert await asyncio.wait_for(messages.get(), 2) == {
                "type": "websocket.close", "code": 1012,
            }
            await asyncio.wait_for(worker, 2)
            assert stopped.is_set()
            with pytest.raises(RuntimeError, match="Retired account socket"):
                await account_sends[0]({"type": "websocket.send", "text": "must not leak"})
            assert messages.empty()
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)

    asyncio.run(exercise())


@pytest.mark.parametrize("url", [
    "/api/v2/dashboard/account-manager/switch",
    "/api/v2/dashboard/account/switch",
])
def test_switch_retires_old_socket_without_new_account_projection(hosted, monkeypatch, url):
    source = hosted.c.published
    headers = {ADMIN_TOKEN_HEADER: ADMIN_TOKEN}

    def mark_projection(bundle, profile):
        # Explicit account/generation markers isolate transport containment
        # from the dashboard's independent projection schema.
        monkeypatch.setattr(
            bundle.application.state.dashboard_live_data_service_v2,
            "get_snapshot",
            lambda: {"profile": profile, "generation": bundle.generation},
        )

    mark_projection(source, "A")
    with hosted.client.websocket_connect(WEBSOCKET_PATH, headers=headers) as old_socket:
        assert old_socket.receive_json() == {
            "event_type": "dashboard_snapshot",
            "data": {"profile": "A", "generation": source.generation},
        }
        response = hosted.client.post(url, json=target(hosted, "B"), headers=headers)
        assert response.status_code == 200, response.text
        current = hosted.c.published
        assert current.generation == source.generation + 1
        mark_projection(current, "B")
        with hosted.client.websocket_connect(WEBSOCKET_PATH, headers=headers) as new_socket:
            snapshot = new_socket.receive_json()
            assert snapshot == {
                "event_type": "dashboard_snapshot",
                "data": {"profile": "B", "generation": current.generation},
            }
            # A target-account broadcast must reach only the new generation.
            update = {"event_type": "dashboard_updated", "data": snapshot["data"]}
            result = hosted.client.portal.call(
                lambda: current.application.state.dashboard_websocket_hub_v2.broadcast(
                    payload=update,
                )
            )
            assert result["messages_sent"] == 1
            assert new_socket.receive_json() == update
            message = old_socket.receive()
            assert message == {"type": "websocket.close", "code": 1012}

    assert source.application.state.dashboard_websocket_hub_v2.get_connection_count() == 0
