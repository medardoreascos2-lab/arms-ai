from __future__ import annotations

import ast
from pathlib import Path


MAIN_PATH = Path("backend/main.py")


def _tree() -> ast.Module:
    return ast.parse(
        MAIN_PATH.read_text(encoding="utf-8"),
        filename=str(MAIN_PATH),
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


def _call_chains(tree: ast.AST) -> list[str]:
    result: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        chain = _chain(node.func)

        if chain:
            result.append(chain)

    return result


def test_cli_uses_canonical_startup_owner() -> None:
    """
    REC-003:
    backend/main.py must delegate process startup through the
    canonical lifecycle wrapper, which delegates to StartupCoordinatorV2.
    """

    calls = _call_chains(_tree())

    expected = "lifecycle_manager.start_from"

    assert expected in calls, (
        "backend/main.py must delegate startup through "
        "lifecycle_manager.start_from(file_path=...); "
        f"observed calls={calls}"
    )


def test_cli_does_not_bypass_persisted_state_with_clean_startup() -> None:
    """
    Clean startup must not bypass the canonical persisted-state decision.
    """

    calls = _call_chains(_tree())

    forbidden = {
        "runtime_context.startup_coordinator.startup_clean",
        "runtime_context.state_recovery_service.recover_from",
        "runtime_context.state_recovery_service.reconcile_pending_from",
        "lifecycle_manager.start_clean",
        "runtime_context."
        "runtime_lifecycle_manager."
        "start_clean",
    }

    violations = sorted(
        forbidden.intersection(calls)
    )

    assert not violations, (
        "backend/main.py bypasses canonical persisted-state startup: "
        f"{violations}"
    )
