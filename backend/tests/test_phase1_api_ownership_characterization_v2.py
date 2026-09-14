"""Phase 1 route-to-lifecycle characterization tests.

These tests inspect the current application wiring without modifying
production code. They intentionally treat the application route graph as the
source of truth for route ownership and preserve the PAPER-only boundary.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import os
import textwrap
from collections.abc import Iterable
from types import ModuleType
from typing import Any

import pytest


APPLICATION_MODULE = "backend.api.app"
BLOCKED_SIGNAL_TEST_MODULE = (
    "backend.tests.test_trade_lifecycle_service_v2"
)

TRADE_SUBMISSION_PATH = "/v2/trades/submit"
EXECUTION_MANAGER_PATH = "/api/v2/dashboard/execution-manager"
EXECUTION_APPROVAL_PATH = "/api/v2/dashboard/execution-approval"
EXECUTION_SIMULATOR_PATH = "/api/v2/dashboard/execution-simulator"

LIFECYCLE_IDENTIFIERS = (
    "TradeLifecycleServiceV2",
    "trade_lifecycle_service_v2",
    "submit_signal",
    "update_position",
)

EXECUTION_IDENTIFIERS = (
    "ExecutionManagerV2",
    "PaperExecutionEngineV2",
    "ExecutionRiskGateV1",
    "ExecutionManager",
    "execution_manager",
    "paper_execution",
    "execution_risk_gate",
)

READ_ONLY_EXECUTION_IDENTIFIERS = (
    "submit_order",
    "execute",
    "open_position",
    "close_position",
    "create_protection",
    "create_group",
)


def _load_application_module() -> ModuleType:
    """Import the application with the repository's required test policy."""
    policy = {
        "ARMS_MAXIMUM_QUOTE_AGE_SECONDS": "30",
        "ARMS_MINIMUM_REWARD_RISK_RATIO": "2",
        "ARMS_MINIMUM_STOP_POINTS": "1",
        "ARMS_MAXIMUM_STOP_POINTS": "100",
        "ARMS_MAXIMUM_SPREAD_POINTS": "5",
        "ARMS_MINIMUM_ATR_POINTS": "1",
        "ARMS_MINIMUM_A_PLUS_PROBABILITY": ".8",
        "ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE": ".8",
        "ARMS_MAXIMUM_SIGNAL_AGE_SECONDS": "300",
        "ARMS_MAXIMUM_OPEN_POSITIONS": "1",
    }

    for key, value in policy.items():
        os.environ.setdefault(key, value)

    return importlib.import_module(APPLICATION_MODULE)


def _application_object(module: ModuleType) -> Any:
    """Return the module-level application or construct one if necessary."""
    application = getattr(module, "app", None)
    if application is not None:
        return application

    create_app = getattr(module, "create_app", None)
    if create_app is None:
        pytest.fail(
            f"{APPLICATION_MODULE} exposes neither 'app' nor 'create_app'"
        )

    return create_app()


def _route_method_names(route: Any) -> set[str]:
    methods = getattr(route, "methods", None)
    if methods:
        return {str(method).upper() for method in methods}

    method = getattr(route, "method", None)
    if method:
        return {str(method).upper()}

    return set()


def _routes(application: Any) -> list[Any]:
    """Return concrete routes, expanding FastAPI included-router wrappers."""
    router = getattr(application, "router", None)
    if router is None:
        pytest.fail("The application does not expose a router")

    concrete: list[Any] = []
    visited: set[int] = set()

    def collect(route: Any) -> None:
        route_id = id(route)
        if route_id in visited:
            return
        visited.add(route_id)

        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            for child in getattr(original_router, "routes", ()):
                collect(child)
            return

        concrete.append(route)

    for route in getattr(router, "routes", ()):
        collect(route)

    return concrete


def _normalize_route_path(path: str) -> str:
    """Normalize equivalent slash-terminated route representations."""
    if not path:
        return "/"
    return path.rstrip("/") or "/"


def _matching_routes(
    application: Any,
    path: str,
    methods: Iterable[str] | None = None,
) -> list[Any]:
    expected_methods = (
        {method.upper() for method in methods} if methods is not None else None
    )
    expected_path = _normalize_route_path(path)
    matches = []

    for route in _routes(application):
        route_path = getattr(route, "path", None)
        if route_path is None:
            continue

        if _normalize_route_path(str(route_path)) != expected_path:
            continue

        route_methods = _route_method_names(route)
        if expected_methods is not None and not (
            route_methods & expected_methods
        ):
            continue

        matches.append(route)

    return matches


def _require_single_route(
    application: Any,
    path: str,
    methods: Iterable[str],
) -> Any:
    matches = _matching_routes(application, path, methods)
    assert matches, (
        f"Expected route {path!r} with one of "
        f"{sorted(method.upper() for method in methods)!r}"
    )
    assert len(matches) == 1, (
        f"Expected exactly one route for {path!r}; found {len(matches)}"
    )
    return matches[0]


def _source_for_object(value: Any) -> str:
    """Return source for a callable, bound method, or source-bearing object."""
    target = getattr(value, "__func__", value)

    try:
        return inspect.getsource(target)
    except (OSError, TypeError):
        return ""


def _closure_values(value: Any) -> list[Any]:
    target = getattr(value, "__func__", value)
    closure = getattr(target, "__closure__", None)
    if not closure:
        return []

    values = []
    for cell in closure:
        try:
            values.append(cell.cell_contents)
        except ValueError:
            continue
    return values


def _callable_graph_source(
    value: Any,
    *,
    depth: int = 2,
    visited: set[int] | None = None,
) -> str:
    """Collect source from an endpoint and its simple closure dependencies."""
    if visited is None:
        visited = set()

    if depth < 0 or id(value) in visited:
        return ""

    visited.add(id(value))
    source = _source_for_object(value)

    for child in _closure_values(value):
        if callable(child):
            source += "\n" + _callable_graph_source(
                child,
                depth=depth - 1,
                visited=visited,
            )

    return source


def _normalized_source(value: Any) -> str:
    return _callable_graph_source(value).lower()


def _endpoint(route: Any) -> Any:
    endpoint = getattr(route, "endpoint", None)
    if endpoint is None:
        pytest.fail(
            f"Route {getattr(route, 'path', '<unknown>')!r} "
            "does not expose an endpoint"
        )
    return endpoint


def _assert_source_mentions(source: str, identifiers: Iterable[str]) -> None:
    normalized = source.lower()
    assert any(identifier.lower() in normalized for identifier in identifiers), (
        "Expected endpoint call graph to contain one of "
        f"{tuple(identifiers)!r}, but no matching identifier was found"
    )


def _ast_names(source: str) -> set[str]:
    if not source:
        return set()

    try:
        tree = ast.parse(inspect.cleandoc(source))
    except SyntaxError:
        return set()

    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def test_required_execution_related_routes_are_registered() -> None:
    """The application exposes each route required by the Phase 1 contract."""
    module = _load_application_module()
    application = _application_object(module)

    _require_single_route(application, TRADE_SUBMISSION_PATH, {"POST"})
    _require_single_route(application, EXECUTION_MANAGER_PATH, {"GET"})
    _require_single_route(application, EXECUTION_APPROVAL_PATH, {"GET"})
    _require_single_route(application, EXECUTION_SIMULATOR_PATH, {"GET"})


def test_trade_submission_route_delegates_to_authoritative_lifecycle() -> None:
    """Trade submission must enter through TradeLifecycleServiceV2."""
    module = _load_application_module()
    application = _application_object(module)
    route = _require_single_route(application, TRADE_SUBMISSION_PATH, {"POST"})
    endpoint = _endpoint(route)
    source = _normalized_source(endpoint)

    _assert_source_mentions(source, LIFECYCLE_IDENTIFIERS)
    assert "submit_signal" in source, (
        "The trade-submission route must delegate to the lifecycle "
        "submit_signal operation rather than directly invoking a broker or "
        "parallel execution engine"
    )

    names = _ast_names(_callable_graph_source(endpoint))
    assert not (
        names & {"BrokerConnectorV2", "PaperBrokerConnectorV2"}
    ), (
        "The trade-submission route must not directly own broker selection; "
        "broker submission belongs behind the authoritative lifecycle path"
    )


@pytest.mark.parametrize(
    ("path", "method"),
    (
        (EXECUTION_MANAGER_PATH, "GET"),
        (EXECUTION_APPROVAL_PATH, "GET"),
        (EXECUTION_SIMULATOR_PATH, "GET"),
    ),
)
def test_execution_manager_approval_and_simulator_routes_are_observational(
    path: str,
    method: str,
) -> None:
    """Read and simulation views must not delegate to mutating execution."""
    module = _load_application_module()
    application = _application_object(module)
    route = _require_single_route(application, path, {method})
    endpoint = _endpoint(route)
    source = _normalized_source(endpoint)

    assert not any(
        identifier.lower() in source
        for identifier in READ_ONLY_EXECUTION_IDENTIFIERS
    ), (
        f"{method} {path} appears to invoke a mutating execution operation. "
        "Dashboard, approval, and simulator views must remain observational."
    )


def test_execution_manager_route_is_a_read_projection() -> None:
    """The execution-manager dashboard must use a read projection."""
    module = _load_application_module()
    application = _application_object(module)
    route = _require_single_route(application, EXECUTION_MANAGER_PATH, {"GET"})
    endpoint = _endpoint(route)
    source = _normalized_source(endpoint)

    _assert_source_mentions(
        source,
        (
            "project_execution_manager",
            "execution_manager_read_projection",
            "get_snapshot",
            "dashboard",
        ),
    )


def test_execution_approval_route_only_validates_or_reports() -> None:
    """Approval views may validate, but cannot submit or fill orders."""
    module = _load_application_module()
    application = _application_object(module)
    route = _require_single_route(application, EXECUTION_APPROVAL_PATH, {"GET"})
    endpoint = _endpoint(route)
    source = _normalized_source(endpoint)

    assert any(
        identifier in source
        for identifier in (
            "validate_execution",
            "executionapproval",
            "approval",
            "dashboard",
        )
    ), "The approval route should expose validation/reporting behavior"

    assert not any(
        identifier.lower() in source
        for identifier in (
            "submit_order",
            "paperexecutionengine",
            "paper_execution",
            "open_position",
            "close_position",
        )
    )


def test_execution_simulator_route_does_not_submit_or_create_state() -> None:
    """The simulator dashboard must not reach broker or financial mutation."""
    module = _load_application_module()
    application = _application_object(module)
    route = _require_single_route(application, EXECUTION_SIMULATOR_PATH, {"GET"})
    endpoint = _endpoint(route)
    source = _normalized_source(endpoint)

    _assert_source_mentions(
        source,
        (
            "simulate_execution",
            "executionsimulator",
            "simulation",
            "dashboard",
        ),
    )

    assert not any(
        identifier.lower() in source
        for identifier in (
            "submit_order",
            "paperexecutionengine",
            "paper_execution",
            "open_position",
            "close_position",
            "create_protection",
            "create_group",
        )
    )


def test_blocked_signal_zero_side_effect_regression_is_collected() -> None:
    """The authoritative blocked-signal regression must remain present."""
    module = importlib.import_module(BLOCKED_SIGNAL_TEST_MODULE)
    test_functions = {
        name: value
        for name, value in vars(module).items()
        if name.startswith("test_") and callable(value)
    }

    blocked_test = next(
        (
            value
            for name, value in test_functions.items()
            if "blocked_signal" in name
            and "execution" in name
        ),
        None,
    )

    assert blocked_test is not None, (
        "The lifecycle regression proving that blocked signals create zero "
        "execution effects must remain available"
    )

    blocked_source = _source_for_object(blocked_test).lower()

    assert "calls.items()" in blocked_source
    assert "execution_state(service)" in blocked_source
    assert "== before" in blocked_source

    module_source = inspect.getsource(module).lower()

    required_evidence = (
        "broker_connector_v2",
        "submit_order",
        "get_orders",
        "get_fills",
        "get_positions",
        "portfolio",
        "trade_journal",
    )

    missing_evidence = [
        probe
        for probe in required_evidence
        if probe not in module_source
    ]

    assert not missing_evidence, (
        "The authoritative lifecycle regression module must retain "
        "broker/portfolio/journal zero-side-effect evidence; "
        f"missing references: {missing_evidence!r}"
    )
