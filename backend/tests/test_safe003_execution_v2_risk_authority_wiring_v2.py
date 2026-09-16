from __future__ import annotations

import ast
from pathlib import Path


SOURCE = Path(
    "backend/services/live_market_analysis_service.py"
)


def _analyze_function() -> ast.FunctionDef:
    tree = ast.parse(
        SOURCE.read_text(encoding="utf-8")
    )

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "analyze"
        ):
            return node

    raise AssertionError(
        "LiveMarketAnalysisService.analyze not found"
    )


def _execution_v2_call(
    analyze: ast.FunctionDef,
) -> ast.Call:
    calls: list[ast.Call] = []

    for node in ast.walk(analyze):
        if not isinstance(node, ast.Call):
            continue

        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "evaluate"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr
            == "execution_decision_engine_v2"
        ):
            calls.append(node)

    assert len(calls) == 1

    return calls[0]


def _keyword(
    call: ast.Call,
    name: str,
) -> ast.AST:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value

    raise AssertionError(
        f"keyword {name!r} not found"
    )


def test_execution_v2_risk_authority_is_resolved_before_boundary():
    analyze = _analyze_function()
    call = _execution_v2_call(analyze)

    risk_value = _keyword(
        call,
        "risk_approved",
    )

    # SAFE-003:
    # Execution V2 must consume an already-resolved
    # runtime authority. It must not recover authority
    # by testing whether a branch-local variable happened
    # to exist.
    assert isinstance(
        risk_value,
        ast.Name,
    )

    assert (
        risk_value.id
        == "account_risk_approved"
    )


def test_execution_v2_has_no_locals_based_risk_authority_fallback():
    analyze = _analyze_function()
    call = _execution_v2_call(analyze)

    risk_value = _keyword(
        call,
        "risk_approved",
    )

    text = ast.unparse(
        risk_value
    )

    assert "locals()" not in text
    assert "else True" not in text
