from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pytest
from fastapi.routing import APIRoute


try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - FastAPI is required by the application.
    TestClient = None  # type: ignore[assignment]


from backend.api.app import create_app


ADMIN_AUTHORIZATION_NAMES = {
    "require_admin_authorization_v2",
    "require_admin_authorization",
    "admin_authorization",
    "admin_authorization_dependency",
}

EXECUTION_MUTATION_PATHS = {
    "/v2/trades/submit",
    "/v2/positions/{position_id}/update",
}

ADMINISTRATIVE_MUTATION_PATHS = {
    "/api/v2/dashboard/account-manager/switch",
    "/api/v2/dashboard/account/switch",
    "/api/v2/market-hours/refresh",
    "/api/v2/backtesting/controller/start",
    "/api/v2/backtesting/controller/stop",
    "/api/v2/backtesting/jobs",
    "/api/v2/backtesting/jobs/process-next",
    "/api/v2/backtesting/jobs/{job_id}",
    "/api/v3/dashboard/market-price",
}

OBSERVATIONAL_PATH_PREFIXES = (
    "/health",
    "/api/v2/dashboard/",
    "/api/v2/market-hours/",
    "/api/v2/backtesting/",
)

OBSERVATIONAL_EXACT_PATHS = {
    "/api/v2/dashboard/live",
    "/api/v2/dashboard/widgets",
    "/api/v2/dashboard/execution-manager",
    "/api/v2/dashboard/risk",
    "/api/v2/dashboard/account-manager",
    "/api/v2/dashboard/account-manager/available",
    "/api/v2/dashboard/account-manager/switch-context",
    "/api/v2/dashboard/execution-simulator",
    "/api/v2/market-hours/status",
    "/api/v2/market-hours/coverage",
    "/api/v2/backtesting/controller/status",
    "/api/v2/backtesting/jobs",
}


@dataclass(frozen=True)
class RouteDescriptor:
    path: str
    methods: frozenset[str]
    endpoint: Any
    dependency_names: frozenset[str]


class MutationProbe:
    """Records calls to execution or financial-state mutation methods."""

    METHOD_NAMES = {
        "add_position",
        "close_position",
        "create_group",
        "create_protection",
        "emit_fill",
        "execute",
        "execute_order",
        "open_position",
        "prepare_order",
        "publish_fill",
        "record_close_trade",
        "record_open_trade",
        "submit",
        "submit_order",
        "switch_account",
        "update_account",
        "update_from_portfolio",
        "update_position",
    }

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self._originals: list[tuple[Any, str, Any]] = []

    def install(self, app: Any) -> None:
        state = getattr(app, "state", None)
        if state is None:
            return

        for owner_name, owner in vars(state).items():
            self._install_on(owner_name, owner)

    def _install_on(self, owner_name: str, owner: Any) -> None:
        if owner is None:
            return

        for method_name in self.METHOD_NAMES:
            method = getattr(owner, method_name, None)
            if not callable(method):
                continue

            try:
                original = getattr(owner, method_name)
            except AttributeError:
                continue

            def guarded(
                *args: Any,
                _owner_name: str = owner_name,
                _method_name: str = method_name,
                _original: Any = original,
                **kwargs: Any,
            ) -> Any:
                self.calls.append((_owner_name, _method_name))
                return _original(*args, **kwargs)

            try:
                setattr(owner, method_name, guarded)
            except (AttributeError, TypeError):
                continue

            self._originals.append((owner, method_name, original))

    def uninstall(self) -> None:
        for owner, method_name, original in reversed(self._originals):
            try:
                setattr(owner, method_name, original)
            except (AttributeError, TypeError):
                pass
        self._originals.clear()


def _iter_routes(app: Any) -> Iterable[APIRoute]:
    visited: set[int] = set()

    def collect(route: Any) -> Iterable[APIRoute]:
        route_id = id(route)
        if route_id in visited:
            return
        visited.add(route_id)

        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            for child in getattr(original_router, "routes", ()):
                yield from collect(child)
            return

        if isinstance(route, APIRoute):
            yield route

    for route in app.routes:
        yield from collect(route)


def _dependency_names(dependant: Any) -> set[str]:
    names: set[str] = set()

    def visit(node: Any) -> None:
        call = getattr(node, "call", None)
        if call is not None:
            names.add(getattr(call, "__name__", call.__class__.__name__))

        for child in getattr(node, "dependencies", ()) or ():
            visit(child)

    visit(dependant)
    return names


def _route_descriptors(app: Any) -> list[RouteDescriptor]:
    return [
        RouteDescriptor(
            path=route.path,
            methods=frozenset(route.methods or set()),
            endpoint=route.endpoint,
            dependency_names=frozenset(_dependency_names(route.dependant)),
        )
        for route in _iter_routes(app)
    ]


def _normalized_path(path: str) -> str:
    if path == "/":
        return path
    return path.rstrip("/")


def _same_path(left: str, right: str) -> bool:
    return _normalized_path(left) == _normalized_path(right)


def _find_routes(app: Any, path: str) -> list[RouteDescriptor]:
    return [
        route
        for route in _route_descriptors(app)
        if _same_path(route.path, path)
    ]


def _has_admin_authorization(route: RouteDescriptor) -> bool:
    normalized = {
        name.lower().replace("-", "_")
        for name in route.dependency_names
    }
    expected = {
        name.lower().replace("-", "_")
        for name in ADMIN_AUTHORIZATION_NAMES
    }
    return bool(normalized.intersection(expected))


def _is_mutating_route(route: RouteDescriptor) -> bool:
    return bool(route.methods.intersection({"POST", "PUT", "PATCH", "DELETE"}))


def _is_observational_route(route: RouteDescriptor) -> bool:
    if "GET" not in route.methods and "HEAD" not in route.methods:
        return False

    normalized_route_path = _normalized_path(route.path)
    normalized_exact_paths = {
        _normalized_path(path)
        for path in OBSERVATIONAL_EXACT_PATHS
    }
    normalized_prefixes = tuple(
        _normalized_path(prefix)
        for prefix in OBSERVATIONAL_PATH_PREFIXES
    )

    return (
        normalized_route_path in normalized_exact_paths
        or any(
            normalized_route_path.startswith(prefix)
            for prefix in normalized_prefixes
        )
    )


@pytest.fixture
def application() -> Any:
    return create_app()


def test_expected_observational_routes_are_registered_once(application: Any) -> None:
    descriptors = _route_descriptors(application)

    for path in OBSERVATIONAL_EXACT_PATHS:
        matches = [
            route
            for route in descriptors
            if _same_path(route.path, path)
            and route.methods.intersection({"GET", "HEAD"})
        ]
        assert len(matches) == 1, (
            f"Expected exactly one observational route for {path!r}; "
            f"found {len(matches)}"
        )


def test_observational_routes_have_no_mutating_http_methods(application: Any) -> None:
    for route in _route_descriptors(application):
        if _is_observational_route(route):
            assert not _is_mutating_route(route), (
                f"Observational route {route.path!r} exposes mutating methods: "
                f"{sorted(route.methods)}"
            )


def test_observational_routes_do_not_require_admin_mutation_authorization(
    application: Any,
) -> None:
    for route in _route_descriptors(application):
        if _is_observational_route(route):
            assert not _has_admin_authorization(route), (
                f"Observational route {route.path!r} unexpectedly carries an "
                "administrative mutation dependency"
            )


@pytest.mark.skipif(TestClient is None, reason="FastAPI TestClient is unavailable")
def test_observational_reads_do_not_call_execution_or_financial_mutations(
    application: Any,
) -> None:
    probe = MutationProbe()
    probe.install(application)

    try:
        client = TestClient(application)
        routes = [
            route
            for route in _route_descriptors(application)
            if _is_observational_route(route)
            and _normalized_path(route.path)
            in {
                _normalized_path(path)
                for path in OBSERVATIONAL_EXACT_PATHS
            }
            and route.methods.intersection({"GET", "HEAD"})
            and "{" not in route.path
        ]

        assert routes, "No concrete observational routes were discovered"

        for route in routes:
            response = client.get(route.path)
            assert response.status_code not in {500, 501}, (
                f"Observational route {route.path!r} failed with "
                f"{response.status_code}: {response.text}"
            )

        assert probe.calls == [], (
            "Observational dashboard/account/risk/intelligence reads invoked "
            f"execution or financial mutations: {probe.calls!r}"
        )
    finally:
        probe.uninstall()


@pytest.mark.parametrize(
    "path",
    sorted(EXECUTION_MUTATION_PATHS | ADMINISTRATIVE_MUTATION_PATHS),
)
def test_execution_and_administrative_mutations_are_admin_protected(
    application: Any,
    path: str,
) -> None:
    matches = _find_routes(application, path)
    assert matches, f"Expected protected mutation route {path!r} is not registered"

    mutating_matches = [
        route for route in matches if _is_mutating_route(route)
    ]
    assert mutating_matches, (
        f"Expected {path!r} to expose a mutating HTTP method"
    )

    for route in mutating_matches:
        assert _has_admin_authorization(route), (
            f"Mutating route {path!r} with methods "
            f"{sorted(route.methods)} lacks the intended admin authorization"
        )


def test_no_known_execution_mutation_route_is_unprotected(
    application: Any,
) -> None:
    descriptors = _route_descriptors(application)

    for route in descriptors:
        if not _is_mutating_route(route):
            continue

        if any(
            _same_path(route.path, execution_path)
            for execution_path in EXECUTION_MUTATION_PATHS
        ):
            assert _has_admin_authorization(route), (
                f"Execution-capable route {route.path!r} is not protected"
            )


@pytest.mark.skipif(TestClient is None, reason="FastAPI TestClient is unavailable")
def test_unauthorized_execution_and_administrative_requests_do_not_reach_handlers(
    application: Any,
) -> None:
    client = TestClient(application)
    paths = sorted(EXECUTION_MUTATION_PATHS | ADMINISTRATIVE_MUTATION_PATHS)

    for path in paths:
        matches = [
            route
            for route in _find_routes(application, path)
            if _is_mutating_route(route)
        ]
        if not matches:
            continue

        concrete_path = path.replace(
            "{position_id}",
            "phase1-test-position",
        )
        concrete_path = concrete_path.replace(
            "{job_id}",
            "phase1-test-job",
        )

        for route in matches:
            method = next(
                iter(route.methods.intersection(
                    {"POST", "PUT", "PATCH", "DELETE"}
                ))
            )
            response = client.request(method, concrete_path, json={})

            assert response.status_code in {401, 403, 404, 405, 422, 503}, (
                f"Unrecognized unauthorized response for {method} {path}: "
                f"{response.status_code} {response.text}"
            )


def test_account_switch_aliases_share_authorization_contract(
    application: Any,
) -> None:
    canonical_path = "/api/v2/dashboard/account-manager/switch"
    alias_path = "/api/v2/dashboard/account/switch"

    canonical = [
        route
        for route in _find_routes(application, canonical_path)
        if _is_mutating_route(route)
    ]
    alias = [
        route
        for route in _find_routes(application, alias_path)
        if _is_mutating_route(route)
    ]

    assert canonical, (
        f"Canonical account-switch route is not registered: {canonical_path}"
    )
    assert alias, (
        f"Account-switch compatibility alias is not registered: {alias_path}"
    )

    canonical_contract = {
        (
            route.methods,
            route.dependency_names,
            getattr(route.endpoint, "__name__", None),
        )
        for route in canonical
    }
    alias_contract = {
        (
            route.methods,
            route.dependency_names,
            getattr(route.endpoint, "__name__", None),
        )
        for route in alias
    }

    assert canonical_contract == alias_contract, (
        "Account-switch compatibility aliases do not preserve the same "
        f"authorization contract: canonical={canonical_contract!r}, "
        f"alias={alias_contract!r}"
    )

    assert all(_has_admin_authorization(route) for route in canonical)
    assert all(_has_admin_authorization(route) for route in alias)


def test_account_switch_aliases_do_not_register_duplicate_unprotected_mutations(
    application: Any,
) -> None:
    descriptors = _route_descriptors(application)

    for path in (
        "/api/v2/dashboard/account-manager/switch",
        "/api/v2/dashboard/account/switch",
    ):
        matches = [
            route
            for route in descriptors
            if _same_path(route.path, path)
            and _is_mutating_route(route)
        ]
        assert len(matches) == 1, (
            f"Account-switch route {path!r} must be registered exactly once; "
            f"found {len(matches)}"
        )
        assert _has_admin_authorization(matches[0])
