"""Phase 1 application-level risk-authority integration tests.

These tests intentionally exercise application composition and route boundaries
without changing production behavior.  They protect the invariant that an
invalid, incomplete, blocked, or unauthorized request cannot reach execution.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest


EXECUTION_ROUTE_PATHS = {
    "/v2/trades/submit",
    "/api/v2/trades/submit",
}

PARALLEL_EXECUTION_NAMES = (
    "ExecutionEngineV2",
    "ExecutionServiceV2",
    "ExecutionPipelineV2",
    "SignalExecutionManager",
    "TradeExecutionEngine",
)

REQUIRED_APP_STATE_AUTHORITIES = (
    "account_state_manager_v2",
    "execution_risk_gate_v1",
    "position_sizing_engine",
    "runtime_quote_authority_v2",
    "price_feed_service_v2",
)


def _all_routes(app: Any) -> list[Any]:
    """Return application routes, including routes nested in mounted routers."""
    routes: list[Any] = []

    def collect(items: Any) -> None:
        for route in items or []:
            routes.append(route)
            nested = getattr(route, "routes", None)
            if nested:
                collect(nested)

    collect(getattr(app, "routes", None))
    return routes


def _execution_routes(app: Any) -> list[Any]:
    return [
        route
        for route in _all_routes(app)
        if getattr(route, "path", None) in EXECUTION_ROUTE_PATHS
        and "POST" in set(getattr(route, "methods", None) or ())
    ]


def _route_source(route: Any) -> str:
    endpoint = getattr(route, "endpoint", None)
    if endpoint is None:
        return ""
    try:
        return inspect.getsource(endpoint)
    except (OSError, TypeError):
        return ""


def _execution_component_names(source: str) -> set[str]:
    return {
        name
        for name in PARALLEL_EXECUTION_NAMES
        if name in source
    }


def _runtime_app():
    """Import the application lazily so collection does not construct it."""
    try:
        from backend.api.app import create_app
    except ImportError as exc:  # pragma: no cover - repository setup failure
        pytest.fail(f"Unable to import the application factory: {exc}")

    return create_app()


def _app_state(app: Any) -> Any:
    state = getattr(app, "state", None)
    assert state is not None, "The application must expose an application state object."
    return state


def _find_lifecycle_service(app: Any) -> Any:
    state = _app_state(app)
    service = getattr(state, "trade_lifecycle_service_v2", None)
    assert service is not None, (
        "The application must publish the canonical "
        "TradeLifecycleServiceV2 in app.state."
    )
    return service


def _find_route(app: Any, path: str) -> Any:
    matches = [
        route
        for route in _all_routes(app)
        if getattr(route, "path", None) == path
        and "POST" in set(getattr(route, "methods", None) or ())
    ]
    assert matches, f"No POST route was registered for {path!r}."
    assert len(matches) == 1, f"Multiple POST routes were registered for {path!r}."
    return matches[0]


def _route_references_lifecycle(route: Any, lifecycle_service: Any) -> bool:
    """Check source and captured dependencies for canonical lifecycle usage."""
    source = _route_source(route)

    if "TradeLifecycleServiceV2" in source or "trade_lifecycle" in source.lower():
        return True

    endpoint = getattr(route, "endpoint", None)
    if endpoint is None:
        return False

    try:
        closure_values = inspect.getclosurevars(endpoint)
    except (OSError, TypeError, ValueError):
        return False

    captured_values = (
        list(closure_values.nonlocals.values())
        + list(closure_values.globals.values())
    )

    return any(
        value is lifecycle_service
        or value.__class__.__name__ == "TradeLifecycleServiceV2"
        for value in captured_values
    )


def _assert_no_execution_component_in_source(source: str) -> None:
    forbidden = _execution_component_names(source)
    assert not forbidden, (
        "The trade-submission route must delegate to the canonical lifecycle "
        f"rather than directly invoking parallel execution abstractions: "
        f"{sorted(forbidden)}"
    )


def _post_invalid_request(app: Any, path: str) -> Any:
    """Submit an intentionally incomplete request.

    FastAPI/Pydantic validation must reject this before any execution service,
    broker, fill, position, or financial-state mutation can be reached.
    """
    try:
        from fastapi.testclient import TestClient
    except ImportError as exc:  # pragma: no cover - dependency failure
        pytest.fail(f"FastAPI TestClient is unavailable: {exc}")

    client = TestClient(app)
    return client.post(path, json={})


def test_trade_submission_route_has_one_canonical_lifecycle_owner() -> None:
    app = _runtime_app()

    routes = _execution_routes(app)
    assert len(routes) == 1, (
        "The application must expose exactly one canonical POST trade-submission "
        "route, without duplicate aliases that could select different execution "
        "pipelines."
    )

    route = routes[0]
    source = _route_source(route)
    lifecycle_service = _find_lifecycle_service(app)

    assert lifecycle_service.__class__.__name__ == "TradeLifecycleServiceV2"
    assert _route_references_lifecycle(route, lifecycle_service), (
        "The application trade-submission route must delegate to "
        "TradeLifecycleServiceV2."
    )
    _assert_no_execution_component_in_source(source)


@pytest.mark.parametrize("path", sorted(EXECUTION_ROUTE_PATHS))
def test_incomplete_trade_submission_fails_before_execution(
    path: str,
) -> None:
    app = _runtime_app()
    routes = [
        route
        for route in _all_routes(app)
        if getattr(route, "path", None) == path
        and "POST" in set(getattr(route, "methods", None) or ())
    ]

    if not routes:
        pytest.skip(f"Compatibility route is not registered: {path}")

    lifecycle_service = _find_lifecycle_service(app)

    execution_calls: list[str] = []

    def fail_if_called(*args: Any, **kwargs: Any) -> None:
        execution_calls.append("lifecycle")
        raise AssertionError("Invalid input reached the lifecycle execution boundary.")

    original_submit = getattr(lifecycle_service, "submit_signal", None)
    if original_submit is None:
        pytest.fail("TradeLifecycleServiceV2 must expose submit_signal().")

    lifecycle_service.submit_signal = fail_if_called
    try:
        response = _post_invalid_request(app, path)
    finally:
        lifecycle_service.submit_signal = original_submit

    assert response.status_code in {400, 401, 403, 422, 503}, response.text
    assert execution_calls == [], (
        "Incomplete application requests must be rejected before the canonical "
        "execution lifecycle is invoked."
    )


def test_application_publishes_required_risk_authorities() -> None:
    app = _runtime_app()
    state = _app_state(app)

    missing = [
        name
        for name in REQUIRED_APP_STATE_AUTHORITIES
        if getattr(state, name, None) is None
    ]

    assert not missing, (
        "The application must publish all required fail-closed authorities in "
        f"app.state; missing: {missing}"
    )


def test_execution_risk_gate_is_reachable_from_canonical_lifecycle() -> None:
    app = _runtime_app()
    lifecycle_service = _find_lifecycle_service(app)
    state = _app_state(app)

    gate = getattr(state, "execution_risk_gate_v1", None)
    assert gate is not None

    lifecycle_values = vars(lifecycle_service)
    lifecycle_objects = list(lifecycle_values.values())

    assert gate in lifecycle_objects or any(
        value is gate
        for value in lifecycle_values.values()
        if value is not None
    ), (
        "TradeLifecycleServiceV2 must use the application-provided "
        "ExecutionRiskGateV1 rather than constructing or bypassing a separate "
        "risk gate."
    )


@pytest.mark.parametrize(
    ("authority_name", "description"),
    [
        ("account_state_manager_v2", "account risk state and daily-loss block"),
        ("execution_risk_gate_v1", "final execution risk gate"),
        ("position_sizing_engine", "position sizing authority"),
        ("runtime_quote_authority_v2", "required supplied quote authority"),
        ("price_feed_service_v2", "price freshness validation"),
    ],
)
def test_required_authority_is_not_silently_absent(
    authority_name: str,
    description: str,
) -> None:
    app = _runtime_app()
    state = _app_state(app)
    authority = getattr(state, authority_name, None)

    assert authority is not None, (
        f"The application must fail closed rather than silently omit "
        f"{description} ({authority_name})."
    )


def test_application_execution_mode_is_paper_only() -> None:
    app = _runtime_app()
    state = _app_state(app)

    observed_modes: list[Any] = []

    for name in (
        "execution_manager_v2",
        "paper_execution_engine_v2",
        "execution_service_v2",
        "execution_engine_v2",
    ):
        component = getattr(state, name, None)
        if component is None:
            continue

        for attribute in ("execution_mode", "mode"):
            if hasattr(component, attribute):
                observed_modes.append(getattr(component, attribute))

    if not observed_modes:
        pytest.fail(
            "The application must expose at least one execution component with "
            "an explicit execution mode."
        )

    assert all(str(mode).upper() == "PAPER" for mode in observed_modes), (
        "Every application-level execution component must remain explicitly "
        f"PAPER-only; observed modes: {observed_modes!r}"
    )


def test_trade_submission_route_does_not_directly_construct_execution_engines() -> None:
    app = _runtime_app()
    route = _find_route(app, "/v2/trades/submit")
    source = _route_source(route)

    forbidden_construction_tokens = (
        "ExecutionEngineV2(",
        "ExecutionServiceV2(",
        "ExecutionPipelineV2(",
        "SignalExecutionManager(",
        "TradeExecutionEngine(",
        "PaperExecutionEngineV2(",
        "PaperBrokerConnectorV2(",
    )

    constructions = [
        token for token in forbidden_construction_tokens if token in source
    ]

    assert not constructions, (
        "The route must not construct execution infrastructure per request. "
        f"Found: {constructions}"
    )


def test_invalid_request_is_not_reported_as_a_successful_execution() -> None:
    app = _runtime_app()
    response = _post_invalid_request(app, "/v2/trades/submit")

    assert response.status_code not in {200, 201, 202}, (
        "An incomplete trade request must never be reported as a successful "
        "execution or accepted trade."
    )

    if "application/json" in response.headers.get("content-type", ""):
        payload = response.json()
        serialized = repr(payload).upper()
        assert "FILLED" not in serialized
        assert "READY_TO_SUBMIT" not in serialized
        assert payload.get("accepted") is not True
        assert payload.get("execution") not in {"FILLED", "READY_TO_SUBMIT"}
