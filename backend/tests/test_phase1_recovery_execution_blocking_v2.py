"""Phase 1 recovery/lifecycle execution-blocking characterization tests.

These tests intentionally do not modify production code. They verify that the
recovery and lifecycle components expose the boundaries required to enforce:

    uncertain or inconsistent state
        -> recovery/reconciliation
        -> semantic validation
        -> runtime readiness
        -> execution remains blocked until success

The tests are deliberately limited to public production contracts. They do not
enable LIVE execution, submit broker orders, or perform destructive recovery.
"""

from __future__ import annotations
import ast

import importlib
import inspect
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _load_class(module_name: str, class_name: str) -> type[Any]:
    """Load a required production class with a useful failure message."""
    module = importlib.import_module(module_name)
    production_class = getattr(module, class_name, None)

    assert production_class is not None, (
        f"{module_name}.{class_name} is required by the Phase 1 recovery "
        "lifecycle contract"
    )
    assert inspect.isclass(production_class), (
        f"{module_name}.{class_name} must be a class"
    )
    return production_class


def _required_methods(production_class: type[Any], *method_names: str) -> None:
    """Assert that a production boundary exposes its required operations."""
    missing = [
        method_name
        for method_name in method_names
        if not callable(getattr(production_class, method_name, None))
    ]

    assert not missing, (
        f"{production_class.__module__}.{production_class.__name__} is missing "
        f"required recovery/lifecycle methods: {', '.join(missing)}"
    )


def _require_any_method(
    production_class: type[Any],
    *method_names: str,
) -> str:
    """Return one supported public method name from a contract group."""
    for method_name in method_names:
        if callable(getattr(production_class, method_name, None)):
            return method_name

    assert False, (
        f"{production_class.__module__}.{production_class.__name__} must expose "
        f"one of the required methods: {', '.join(method_names)}"
    )


def _source_for(production_class: type[Any]) -> str:
    """Return the source for a class, failing instead of silently skipping."""
    try:
        return inspect.getsource(production_class)
    except (OSError, TypeError) as exc:
        raise AssertionError(
            f"Source for {production_class.__module__}."
            f"{production_class.__name__} could not be inspected"
        ) from exc


def test_durable_state_boundary_exposes_fail_closed_operation() -> None:
    """Durable state must expose an explicit unsafe-state boundary."""
    durable_state = _load_class(
        "backend.services.durable_execution_state_v2",
        "DurableExecutionStateV2",
    )

    _required_methods(
        durable_state,
        "fail_closed",
    )

    source = _source_for(durable_state).lower()
    assert "fail_closed" in source
    assert any(
        token in source
        for token in (
            "pending",
            "inconsistent",
            "invalid",
            "corrupt",
            "checksum",
        )
    ), "Durable state must distinguish unsafe or incomplete state"


def test_execution_state_store_exposes_load_validation_and_restoration_boundaries() -> None:
    """State loading must be followed by validation and restoration."""
    state_store = _load_class(
        "backend.services.execution_state_store_v2",
        "ExecutionStateStoreV2",
    )

    _required_methods(
        state_store,
        "load",
        "validate",
        "restore",
    )

    source = _source_for(state_store).lower()
    assert "load" in source
    assert "validate" in source
    assert "restore" in source


def test_pending_operation_reconciliation_exposes_explicit_reconciliation() -> None:
    """Pending operations must be classified/reconciled, not silently ignored."""
    reconciler = _load_class(
        "backend.services.pending_operation_reconciliation_v2",
        "PendingOperationReconciliationV2",
    )

    _required_methods(
        reconciler,
        "reconcile",
    )

    source = _source_for(reconciler).lower()
    assert "reconcil" in source
    assert any(
        token in source
        for token in (
            "ambiguous",
            "pending",
            "partial",
            "corrupt",
            "executed",
        )
    ), "Reconciliation must distinguish unsafe pending-operation outcomes"


def test_recovery_service_exposes_recovery_and_validation_contract() -> None:
    """Recovery must reconstruct state and validate it before readiness."""
    recovery_service = _load_class(
        "backend.services.state_recovery_service_v2",
        "StateRecoveryServiceV2",
    )

    _required_methods(
        recovery_service,
        "recover",
    )

    source = _source_for(recovery_service).lower()
    assert any(
        token in source
        for token in (
            "validate",
            "semantic",
            "inconsistent",
            "fail_closed",
            "blocked",
        )
    ), "Recovery must validate state and fail closed on unsafe state"


def test_recovery_semantic_validation_exposes_consistency_validation() -> None:
    """Semantic validation must be an explicit recovery boundary."""
    semantic_validator = _load_class(
        "backend.services.recovery_semantic_validation_v2",
        "RecoverySemanticValidationV2",
    )

    validation_methods = (
        "validate",
        "validate_state",
        "validate_recovery",
        "validate_snapshot",
    )
    _require_any_method(semantic_validator, *validation_methods)

    source = _source_for(semantic_validator).lower()
    assert any(
        token in source
        for token in (
            "account",
            "portfolio",
            "journal",
            "position",
            "fill",
            "generation",
            "execution_mode",
        )
    ), "Semantic validation must inspect operational state consistency"


def test_runtime_lifecycle_exposes_startup_shutdown_and_failure_states() -> None:
    """Runtime readiness must be controlled by the lifecycle state machine."""
    lifecycle = _load_class(
        "backend.services.runtime_lifecycle_manager_v2",
        "RuntimeLifecycleManagerV2",
    )

    _required_methods(
        lifecycle,
        "start_from",
        "shutdown_to",
    )

    source = _source_for(lifecycle).lower()
    assert "failed" in source
    assert "starting" in source
    assert "stopping" in source
    assert "running" in source


def test_startup_coordinator_exposes_recovery_selection_and_fail_closed_path() -> None:
    """Startup must not treat an existing or unsafe snapshot as clean state."""
    startup = _load_class(
        "backend.services.startup_coordinator_v2",
        "StartupCoordinatorV2",
    )

    _required_methods(
        startup,
        "start_clean",
        "start_from",
    )

    source = _source_for(startup).lower()
    assert any(
        token in source
        for token in (
            "recover",
            "snapshot",
            "state_path",
        )
    ), "Startup must inspect persisted state and select recovery behavior"
    assert any(
        token in source
        for token in (
            "fail_closed",
            "failed",
            "blocked",
            "raise",
        )
    ), "Unsafe startup state must fail closed"


def test_graceful_shutdown_exposes_durable_persistence_boundary() -> None:
    """Shutdown must persist state before the runtime is considered stopped."""
    shutdown = _load_class(
        "backend.services.graceful_shutdown_service_v2",
        "GracefulShutdownServiceV2",
    )

    shutdown_methods = (
        "shutdown",
        "shutdown_to",
        "persist",
        "save",
    )
    _require_any_method(shutdown, *shutdown_methods)

    source = _source_for(shutdown).lower()
    assert any(
        token in source
        for token in (
            "save",
            "persist",
            "checkpoint",
            "snapshot",
        )
    ), "Graceful shutdown must persist a final durable state"


def test_recovery_lifecycle_modules_preserve_paper_only_boundary() -> None:
    """Recovery must not introduce LIVE execution into the PAPER runtime."""
    modules_and_classes = (
        (
            "backend.services.runtime_context_v2",
            "RuntimeContextV2",
        ),
        (
            "backend.services.state_recovery_service_v2",
            "StateRecoveryServiceV2",
        ),
        (
            "backend.services.runtime_lifecycle_manager_v2",
            "RuntimeLifecycleManagerV2",
        ),
    )

    sources = [
        _source_for(_load_class(module_name, class_name)).lower()
        for module_name, class_name in modules_and_classes
    ]
    combined_source = "\n".join(sources)

    assert "paper" in combined_source
    assert "live" not in combined_source or any(
        phrase in combined_source
        for phrase in (
            "not enabled",
            "disabled",
            "blocked",
            "reject",
            "fail_closed",
        )
    ), (
        "Recovery/lifecycle code must not expose an unguarded LIVE execution "
        "path"
    )


def test_recovery_contract_has_no_placeholder_test_body() -> None:
    """Guard against regressing this module to an empty test file."""
    test_source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(test_source)

    test_functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name.startswith("test_")
    ]

    assert len(test_functions) >= 8

    placeholder_nodes = [
        node
        for test_function in test_functions
        for node in ast.walk(test_function)
        if isinstance(node, ast.Pass)
    ]

    assert not placeholder_nodes
