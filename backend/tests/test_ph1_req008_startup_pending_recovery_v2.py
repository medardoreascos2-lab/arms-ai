from __future__ import annotations

import ast
from pathlib import Path


STARTUP_PATH = Path(
    "backend/services/startup_coordinator_v2.py"
)


def _tree() -> ast.Module:
    return ast.parse(
        STARTUP_PATH.read_text(encoding="utf-8"),
        filename=str(STARTUP_PATH),
    )


def _chain(node: ast.AST) -> str:
    parts: list[str] = []
    current = node

    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value

    if isinstance(current, ast.Name):
        parts.append(current.id)

    return ".".join(reversed(parts))


def _startup_from_calls() -> list[str]:
    tree = _tree()

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue

        if node.name != "startup_from":
            continue

        return [
            _chain(child.func)
            for child in ast.walk(node)
            if isinstance(child, ast.Call)
            and _chain(child.func)
        ]

    raise AssertionError(
        "StartupCoordinatorV2.startup_from was not found"
    )


def test_startup_from_recovers_persisted_state() -> None:
    calls = _startup_from_calls()

    assert any(
        call.endswith(".recover_from")
        for call in calls
    ), (
        "startup_from must recover persisted state before "
        "startup can complete."
    )


def test_startup_from_reconciles_pending_operation() -> None:
    calls = _startup_from_calls()

    assert any(
        call.endswith(".reconcile_pending_from")
        for call in calls
    ), (
        "PH1-REQ-008: startup_from must reconcile any "
        "persisted pending operation before startup can "
        "be considered recovered."
    )
