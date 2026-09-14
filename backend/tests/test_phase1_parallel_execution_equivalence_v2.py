"""Phase 1 characterization tests for parallel execution-path safety.

These tests inspect current production wiring and source contracts. They do not
promote parallel or legacy abstractions to authoritative status, modify
production code, or enable LIVE execution.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Iterable

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

CANONICAL_LIFECYCLE_MODULE = "backend.services.trade_lifecycle_service_v2"
CANONICAL_LIFECYCLE_CLASS = "TradeLifecycleServiceV2"

EXECUTION_PATHS = (
    ("backend.execution.execution_service_v2", "ExecutionServiceV2"),
    ("backend.execution.execution_engine_v2", "ExecutionEngineV2"),
    ("backend.execution.execution_pipeline_v2", "ExecutionPipelineV2"),
    ("backend.execution.signal_execution_manager", "SignalExecutionManager"),
    ("backend.execution.trade_execution_engine", "TradeExecutionEngine"),
)

ADMISSION_ONLY_PATHS = {
    "SignalExecutionManager",
}

TRADE_SUBMISSION_ROUTE_MODULE = "backend.api.trade_lifecycle_api_v2"

# These are safety-boundary terms, not an assertion that every component owns
# all of these responsibilities. The test only requires that an execution
# implementation visibly delegates to or enforces the relevant boundary.
ADMISSION_TERMS = (
    "accepted",
    "approved",
    "blocked",
    "rejected",
    "admission",
    "authorize",
    "authorization",
)

RISK_TERMS = (
    "risk",
    "gate",
    "validator",
    "validate",
    "exposure",
    "drawdown",
    "daily_loss",
)

PAPER_TERMS = (
    "paper",
    "simulation",
    "simulated",
    "simulada",
    "simulado",
    "execution_mode",
)

# Some parallel services do not select an execution mode themselves. They
# delegate execution to an injected execution engine. That delegation is the
# service's observable execution boundary and must remain separate from direct
# order submission.
PAPER_DELEGATION_TERMS = (
    "execution_engine",
    "paper_execution_engine",
    "paperbroker",
    "paper_execution",
)

LIVE_BLOCK_TERMS = (
    "live",
    "real_money",
    "real-money",
    "broker",
)

DIRECT_SUBMISSION_NAMES = {
    "submit_order",
    "submit",
    "place_order",
    "send_order",
    "execute_order",
}


@dataclass(frozen=True)
class PathSource:
    module_name: str
    class_name: str
    module: ModuleType
    source: str
    tree: ast.AST


def _load_module(module_name: str) -> ModuleType:
    try:
        return importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - failure is reported clearly
        pytest.fail(f"Could not import execution path {module_name}: {exc}")


def _load_path_source(module_name: str, class_name: str) -> PathSource:
    module = _load_module(module_name)
    implementation = getattr(module, class_name, None)
    assert implementation is not None, (
        f"{module_name} does not expose the expected execution abstraction "
        f"{class_name}"
    )

    try:
        source = inspect.getsource(implementation)
    except (OSError, TypeError) as exc:
        pytest.fail(
            f"Could not inspect {module_name}.{class_name}; "
            f"characterization cannot establish its safety boundary: {exc}"
        )

    return PathSource(
        module_name=module_name,
        class_name=class_name,
        module=module,
        source=source,
        tree=ast.parse(source),
    )


def _normalized_source(source: str) -> str:
    return source.casefold().replace("-", "_").replace(" ", "_")


def _contains_any(source: str, terms: Iterable[str]) -> bool:
    normalized = _normalized_source(source)
    return any(term.casefold().replace("-", "_") in normalized for term in terms)


def _has_paper_boundary(source: str) -> bool:
    """Return whether a path exposes or delegates to a PAPER boundary.

    A service may enforce PAPER mode directly, or it may delegate execution to
    an injected execution engine. The latter is valid only when the service
    does not directly submit orders; direct submission is checked separately.
    """

    if _contains_any(source, PAPER_TERMS):
        return True

    return (
        _contains_any(source, PAPER_DELEGATION_TERMS)
        and _contains_any(source, ("execute", "execution"))
    )


def _has_delegated_execution_boundary(source: str) -> bool:
    """Return whether the path delegates execution to another component.

    Delegating services may not contain broker or LIVE terminology because
    mode enforcement belongs to the injected execution boundary. Their safety
    contract is characterized by the delegated execution reference together
    with the separate prohibition on direct order submission.
    """

    return (
        _contains_any(source, PAPER_DELEGATION_TERMS)
        and _contains_any(source, ("execute", "execution"))
    )


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function = node.func
            if isinstance(function, ast.Name):
                names.add(function.id)
            elif isinstance(function, ast.Attribute):
                names.add(function.attr)
    return names


def _module_source(module_name: str) -> str:
    module = _load_module(module_name)
    try:
        return inspect.getsource(module)
    except (OSError, TypeError) as exc:
        pytest.fail(
            f"Could not inspect module {module_name}; "
            f"characterization cannot establish route ownership: {exc}"
        )


def _source_path(module_name: str) -> Path:
    module = _load_module(module_name)
    module_file = getattr(module, "__file__", None)
    assert module_file, f"{module_name} has no inspectable source file"
    return Path(module_file).resolve()


def _direct_submission_calls(tree: ast.AST) -> set[str]:
    return _called_names(tree) & DIRECT_SUBMISSION_NAMES


def _source_has_class(module_source: str, class_name: str) -> bool:
    tree = ast.parse(module_source)
    return any(
        isinstance(node, ast.ClassDef) and node.name == class_name
        for node in ast.walk(tree)
    )


def test_execution_equivalence_file_is_collected() -> None:
    """The regression file must contain executable pytest tests.

    This guards against the previous empty-file failure where pytest reported
    that no tests ran.
    """

    assert __file__.endswith(
        "test_phase1_parallel_execution_equivalence_v2.py"
    )


def test_canonical_lifecycle_exposes_the_required_safety_boundaries() -> None:
    path = _load_path_source(
        CANONICAL_LIFECYCLE_MODULE,
        CANONICAL_LIFECYCLE_CLASS,
    )

    assert "submit_signal" in path.source, (
        "The canonical lifecycle must expose signal submission for "
        "characterization"
    )
    assert _contains_any(path.source, ADMISSION_TERMS), (
        "Canonical lifecycle has no inspectable admission/rejection boundary"
    )
    assert _contains_any(path.source, RISK_TERMS), (
        "Canonical lifecycle has no inspectable risk or validation boundary"
    )
    assert _contains_any(path.source, PAPER_TERMS), (
        "Canonical lifecycle has no inspectable PAPER/simulation boundary"
    )


@pytest.mark.parametrize(
    ("module_name", "class_name"),
    EXECUTION_PATHS,
    ids=[class_name for _, class_name in EXECUTION_PATHS],
)
def test_parallel_execution_paths_are_explicitly_safety_bounded(
    module_name: str,
    class_name: str,
) -> None:
    """Characterize every retained execution abstraction without promoting it.

    Each abstraction must expose enough source-level evidence to show that it
    participates in admission/risk handling and recognizes or delegates to the
    PAPER boundary. A missing safety contract is a test failure, not permission
    to use the path.
    """

    path = _load_path_source(module_name, class_name)

    assert _contains_any(path.source, ADMISSION_TERMS), (
        f"{module_name}.{class_name} does not expose an inspectable "
        "admission/rejection boundary"
    )
    direct_calls = _direct_submission_calls(path.tree)

    if class_name in ADMISSION_ONLY_PATHS:
        assert not direct_calls, (
            f"{module_name}.{class_name} is an admission-only component "
            f"but directly invokes submission operations {sorted(direct_calls)}"
        )
        assert _contains_any(
            path.source,
            ("duplicate", "cooldown", "wait", "approved", "accepted"),
        ), (
            f"{module_name}.{class_name} does not expose its expected "
            "signal-admission/cooldown boundary"
        )
        return

    assert _contains_any(path.source, RISK_TERMS), (
        f"{module_name}.{class_name} does not expose an inspectable "
        "risk/validation boundary"
    )
    assert _has_paper_boundary(path.source), (
        f"{module_name}.{class_name} does not expose or delegate to an "
        "inspectable PAPER/simulation boundary"
    )
    has_explicit_mode_boundary = _contains_any(path.source, LIVE_BLOCK_TERMS)
    has_delegated_boundary = _has_delegated_execution_boundary(path.source)

    has_explicit_paper_boundary = _contains_any(
        path.source,
        PAPER_TERMS,
    )

    assert (
        has_explicit_mode_boundary
        or (has_delegated_boundary and not direct_calls)
        or (has_explicit_paper_boundary and not direct_calls)
    ), (
        f"{module_name}.{class_name} does not expose an inspectable "
        "PAPER/LIVE boundary, safe delegated execution boundary, or "
        "explicitly simulated no-submission boundary"
    )


@pytest.mark.parametrize(
    ("module_name", "class_name"),
    EXECUTION_PATHS,
    ids=[class_name for _, class_name in EXECUTION_PATHS],
)
def test_parallel_paths_do_not_directly_submit_orders(
    module_name: str,
    class_name: str,
) -> None:
    """Parallel abstractions must not bypass the canonical submission owner.

    Direct order submission from an unresolved parallel abstraction would make
    it an independent execution path and could bypass the canonical lifecycle,
    authorization, and final risk gate.
    """

    path = _load_path_source(module_name, class_name)
    direct_calls = _direct_submission_calls(path.tree)

    assert not direct_calls, (
        f"{module_name}.{class_name} directly invokes order-submission "
        f"operation(s) {sorted(direct_calls)}; it must delegate through the "
        "characterized lifecycle boundary instead"
    )


def test_trade_submission_route_contains_the_canonical_lifecycle_boundary() -> None:
    """The execution-capable API route must be tied to the lifecycle service."""

    module_source = _module_source(TRADE_SUBMISSION_ROUTE_MODULE)
    lifecycle_source = _module_source(CANONICAL_LIFECYCLE_MODULE)

    assert _source_has_class(module_source, "TradeLifecycleRouter") or (
        "TradeLifecycleServiceV2" in module_source
    ), (
        "Trade-submission API module does not expose an inspectable reference "
        "to the canonical lifecycle service"
    )
    assert "TradeLifecycleServiceV2" in module_source, (
        "The trade-submission API route must reference "
        "TradeLifecycleServiceV2"
    )
    assert "submit_signal" in lifecycle_source, (
        "The canonical lifecycle service must expose submit_signal"
    )


def test_trade_submission_route_has_an_explicit_paper_boundary() -> None:
    """The API route must delegate to the canonical PAPER-bounded lifecycle."""

    route_source = _module_source(TRADE_SUBMISSION_ROUTE_MODULE)
    lifecycle_source = _module_source(CANONICAL_LIFECYCLE_MODULE)
    normalized = _normalized_source(route_source)

    assert "TradeLifecycleServiceV2" in route_source
    assert "submit_signal" in route_source

    assert "PaperExecutionEngineV2" in lifecycle_source, (
        "Canonical lifecycle does not expose its required PAPER execution "
        "engine boundary"
    )
    assert (
        "PaperBrokerConnectorV2" in lifecycle_source
        or "paper_execution_engine" in lifecycle_source
    ), (
        "Canonical lifecycle does not expose an inspectable PAPER "
        "broker/execution boundary"
    )

    live_selection_terms = (
        "execution_mode=\"live\"",
        "execution_mode='live'",
        "mode=\"live\"",
        "mode='live'",
        "broker_mode=\"live\"",
        "broker_mode='live'",
    )
    assert not any(term in normalized for term in live_selection_terms), (
        "Trade-submission API route contains an explicit LIVE selection"
    )


def test_canonical_and_parallel_paths_have_distinct_ownership_contracts() -> None:
    """Parallel classes remain candidates, not alternate authorities."""

    lifecycle = _load_path_source(
        CANONICAL_LIFECYCLE_MODULE,
        CANONICAL_LIFECYCLE_CLASS,
    )

    assert "submit_signal" in lifecycle.source

    for module_name, class_name in EXECUTION_PATHS:
        path = _load_path_source(module_name, class_name)

        # This deliberately checks delegation-oriented ownership rather than
        # requiring the parallel class to duplicate the lifecycle API.
        direct_calls = _direct_submission_calls(path.tree)
        assert not direct_calls, (
            f"{module_name}.{class_name} appears to own direct submission "
            f"through {sorted(direct_calls)} instead of remaining behind the "
            "canonical lifecycle boundary"
        )


def test_execution_modules_are_repository_files() -> None:
    """Ensure characterization is against the current repository modules."""

    expected_paths = [
        _source_path(CANONICAL_LIFECYCLE_MODULE),
        *(_source_path(module_name) for module_name, _ in EXECUTION_PATHS),
    ]

    for path in expected_paths:
        assert path.is_file(), f"Expected production source file is missing: {path}"
        assert REPOSITORY_ROOT in path.parents, (
            f"Execution source is outside the repository: {path}"
        )
