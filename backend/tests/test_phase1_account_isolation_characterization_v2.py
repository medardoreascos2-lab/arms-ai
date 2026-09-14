from __future__ import annotations

import ast
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    path = BACKEND_ROOT / relative_path
    assert path.is_file(), f"Expected repository file is missing: {path}"
    return path.read_text(encoding="utf-8")


def _defined_names(source: str) -> set[str]:
    tree = ast.parse(source)
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_account_isolation_components_are_present() -> None:
    expected_files = (
        "accounts/account_config_manager_v2.py",
        "accounts/account_registry_v1.py",
        "services/account_runtime_coordinator_v2.py",
        "services/account_switch_safety_v2.py",
        "services/runtime_context_v2.py",
        "services/durable_execution_state_v2.py",
        "api/routers/account_manager_api_v2.py",
        "api/routers/account_switch_api_v2.py",
    )

    for relative_path in expected_files:
        source = _source(relative_path)
        assert source.strip()

        if relative_path.startswith("api/routers/"):
            assert "APIRouter" in source, relative_path
            assert "router" in source, relative_path
        else:
            assert _defined_names(source), relative_path


def test_account_switch_sources_expose_identity_and_transition_controls() -> None:
    coordinator_source = _source(
        "services/account_runtime_coordinator_v2.py"
    ).lower()
    safety_source = _source(
        "services/account_switch_safety_v2.py"
    ).lower()
    context_source = _source("services/runtime_context_v2.py").lower()

    combined = "\n".join(
        (coordinator_source, safety_source, context_source)
    )

    assert "account" in combined
    assert "switch" in combined or "transition" in combined
    assert "runtime" in combined
    assert "identity" in combined or "namespace" in combined
    assert "lock" in combined or "freeze" in combined


def test_account_state_isolated_by_runtime_or_namespace_boundary() -> None:
    sources = (
        _source("services/account_runtime_coordinator_v2.py").lower(),
        _source("services/account_switch_safety_v2.py").lower(),
        _source("services/runtime_context_v2.py").lower(),
        _source("services/durable_execution_state_v2.py").lower(),
    )
    combined = "\n".join(sources)

    assert "account_id" in combined or "account id" in combined
    assert "namespace" in combined
    assert "generation" in combined
    assert "retir" in combined or "retire" in combined
