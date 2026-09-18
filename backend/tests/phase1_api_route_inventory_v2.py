"""Inspection helpers for the reviewed PH1-REQ-009 manifest (no runtime hooks)."""
import ast
import hashlib
import inspect
import json
from pathlib import Path
import textwrap

from fastapi.routing import APIRoute, APIWebSocketRoute

from backend.api.admin_authorization_dependency_v2 import require_admin_authorization_v2


MANIFEST = Path(__file__).with_name("phase1_api_route_inventory_v2.json")


def routes(application):
    """Preserve registrations, including aliases; never deduplicate by endpoint."""
    def expand(items):
        for route in items:
            included = getattr(route, "original_router", None)
            if included is not None:
                yield from expand(included.routes)
            else:
                yield route

    return list(expand(application.routes))


def key(route):
    return (route.path, tuple(sorted(getattr(route, "methods", ()) or ["WS"])))


def dependencies(route):
    def walk(node):
        if getattr(node, "call", None) is not None:
            yield node.call
        for child in getattr(node, "dependencies", ()):
            yield from walk(child)

    return set(walk(getattr(route, "dependant", None)))


def endpoint_evidence(endpoint):
    """Inspect endpoint and same-module helpers, including imperative state reads."""
    sources, state_fields, calls = [], set(), set()
    seen = set()

    def inspect_function(function):
        if function in seen:
            return
        seen.add(function)
        source = textwrap.dedent(inspect.getsource(function))
        tree = ast.parse(source)
        # Decorators register the function; they are not execution ownership.
        tree.body[0].decorator_list = []
        sources.append(ast.dump(tree, include_attributes=False))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                value = ast.unparse(node)
                for prefix in ("request.app.state.", "websocket.app.state."):
                    if value.startswith(prefix):
                        state_fields.add(value[len(prefix):].split(".")[0])
            if not isinstance(node, ast.Call):
                continue
            calls.add(ast.unparse(node.func))
            if (isinstance(node.func, ast.Name) and node.func.id == "getattr"
                    and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)
                    and ast.unparse(node.args[0]) in {"request.app.state", "websocket.app.state"}):
                state_fields.add(node.args[1].value)
            if isinstance(node.func, ast.Name):
                helper = function.__globals__.get(node.func.id)
                if inspect.isfunction(helper) and helper.__module__ == endpoint.__module__:
                    inspect_function(helper)

    inspect_function(endpoint)
    return {
        "source_sha256": hashlib.sha256("\n".join(sources).encode()).hexdigest(),
        "state_fields": sorted(state_fields),
        "calls": sorted(calls),
    }


def describe(route, application):
    endpoint = route.endpoint
    closure = inspect.getclosurevars(endpoint).nonlocals
    state = application.state._state
    owners = {}
    for name, value in closure.items():
        if name == "self" and endpoint.__module__.startswith("fastapi."):
            continue
        owners[name] = {
            "type": type(value).__module__ + "." + type(value).__name__,
            "state_bindings": sorted(k for k, v in state.items() if v is value) if value is not None else [],
        }
    result = {
        "methods": list(key(route)[1]), "path": route.path, "name": route.name,
        "endpoint": endpoint.__module__ + "." + endpoint.__name__,
        "module": endpoint.__module__,
        "transport": "WEBSOCKET" if isinstance(route, APIWebSocketRoute) else "HTTP",
        "canonical_admin_dependency": require_admin_authorization_v2 in dependencies(route),
        "closure_owners": owners,
    }
    if isinstance(route, (APIRoute, APIWebSocketRoute)):
        result.update(endpoint_evidence(endpoint))
    return result


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def certificate(rows):
    return {
        "TOTAL_RELEVANT_ROUTES": len(rows),
        "CLASSIFIED_ROUTES": sum(bool(row["classification"]) for row in rows),
        "UNCLASSIFIED_ROUTES": sum(not row["classification"] for row in rows),
        "ACCOUNT_SCOPED_ROUTES": sum(row["account_scope"] in {"ACTIVE_RUNTIME", "EXPLICIT_ACCOUNT"} for row in rows),
        "ADMIN_REQUIRED_ROUTES": sum(row["authorization"] == "ADMIN" for row in rows),
        "OBSERVATIONAL_ROUTES": sum(row["mutation"] == "NONE" for row in rows),
        "EXECUTION_BOUNDARY_ROUTES": sum(row["classification"] == "EXECUTION_BOUNDARY" for row in rows),
    }
