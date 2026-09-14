from __future__ import annotations

import ast
from pathlib import Path

from backend.services.runtime_context_v2 import (
    RuntimeContextV2,
    build_runtime_context,
)
from backend.services.runtime_lifecycle_manager_v2 import (
    RuntimeLifecycleManagerV2,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    path = BACKEND_ROOT / relative_path
    assert path.is_file(), f"Expected repository file is missing: {path}"
    return path.read_text(encoding="utf-8")


def _defined_names(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)

    return names


def test_runtime_entrypoints_are_present_and_distinct() -> None:
    asgi_source = _source("api/asgi.py")
    api_source = _source("api/app.py")
    main_source = _source("main.py")

    assert "create_asgi_app" in asgi_source
    assert "create_app" in api_source
    assert "def main" in main_source or "async def main" in main_source

    assert asgi_source != api_source
    assert main_source != api_source


def test_runtime_lifecycle_components_have_expected_boundaries() -> None:
    lifecycle_names = _defined_names(
        _source("services/runtime_lifecycle_manager_v2.py")
    )
    startup_names = _defined_names(
        _source("services/startup_coordinator_v2.py")
    )
    context_names = _defined_names(
        _source("services/runtime_context_v2.py")
    )

    assert any("Lifecycle" in name for name in lifecycle_names)
    assert any("Startup" in name for name in startup_names)
    assert any("Context" in name for name in context_names)

    lifecycle_source = _source("services/runtime_lifecycle_manager_v2.py")
    startup_source = _source("services/startup_coordinator_v2.py")

    assert "start" in lifecycle_source.lower()
    assert "shutdown" in lifecycle_source.lower()
    assert "recover" in startup_source.lower()


def test_runtime_composition_preserves_paper_boundary() -> None:
    context_source = _source("services/runtime_context_v2.py")
    api_source = _source("api/app.py")
    main_source = _source("main.py")

    combined_source = "\n".join((context_source, api_source, main_source))
    normalized = combined_source.upper()

    assert "PAPER" in normalized
    assert "LIVE" in normalized

    # This is a source-level characterization: runtime composition must
    # represent LIVE as a guarded or unavailable mode rather than silently
    # selecting it as the default.
    assert any(
        marker in normalized
        for marker in (
            "LIVE REMAIN",
            "LIVE_EXECUTION",
            "EXECUTION_MODE",
            "PAPER-ONLY",
            "PAPER_ONLY",
        )
    )


def test_runtime_context_has_one_core_lifecycle_authority() -> None:
    context = build_runtime_context()

    assert isinstance(context, RuntimeContextV2)
    assert isinstance(
        context.runtime_lifecycle_manager,
        RuntimeLifecycleManagerV2,
    )

    assert (
        context.runtime_lifecycle_manager.startup_coordinator
        is context.startup_coordinator
    )
    assert (
        context.runtime_lifecycle_manager.graceful_shutdown_service
        is context.graceful_shutdown_service
    )
    assert (
        context.startup_coordinator.state_recovery_service
        is context.state_recovery_service
    )
    assert (
        context.state_recovery_service.execution_state_store
        is context.execution_state_store
    )
    assert (
        context.graceful_shutdown_service.execution_state_store
        is context.execution_state_store
    )


def test_application_reuses_injected_runtime_context_core_services() -> None:
    from backend.api.app import create_app

    context = build_runtime_context()
    app = create_app(runtime_context=context)

    assert app.state.runtime_context_v2 is context
    assert (
        app.state.trade_lifecycle_service_v2
        is context.trade_lifecycle_service
    )

    assert (
        app.state.execution_manager_v2
        is context.execution_manager
    )
    assert (
        app.state.paper_execution_engine_v2
        is context.paper_execution_engine
    )
    assert (
        app.state.broker_connector_v2
        is context.trade_lifecycle_service.broker_connector_v2
    )
    assert (
        app.state.position_manager
        is context.position_manager
    )
    assert (
        app.state.portfolio_manager_v2
        is context.portfolio_manager_v2
    )
    assert (
        app.state.account_state_manager_v2
        is context.account_state_manager_v2
    )
    assert (
        app.state.trade_journal_v2
        is context.trade_lifecycle_service.trade_journal_v2
    )

    assert (
        app.state.account_switch_safety_v2
        is context.account_switch_safety_v2
    )


def test_application_core_services_share_the_injected_lifecycle_graph() -> None:
    from backend.api.app import create_app

    context = build_runtime_context()
    app = create_app(runtime_context=context)
    lifecycle = context.trade_lifecycle_service

    assert app.state.execution_manager_v2 is lifecycle.execution_manager
    assert (
        app.state.paper_execution_engine_v2
        is lifecycle.paper_execution_engine
    )
    assert (
        app.state.portfolio_manager_v2
        is lifecycle.portfolio_manager_v2
    )
    assert (
        app.state.trade_journal_v2
        is lifecycle.trade_journal_v2
    )

    assert context.runtime_lifecycle_manager is not None
    assert context.startup_coordinator is not None
    assert context.state_recovery_service is not None
    assert context.execution_state_store is not None
