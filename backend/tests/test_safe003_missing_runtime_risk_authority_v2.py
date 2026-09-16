from __future__ import annotations

import ast
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "live_market_analysis_service.py"
)


def _execution_v2_call() -> ast.Call:
    tree = ast.parse(
        SOURCE.read_text(encoding="utf-8")
    )

    calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if (
            isinstance(func, ast.Attribute)
            and func.attr == "evaluate"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "execution_decision_engine_v2"
        ):
            calls.append(node)

    assert len(calls) == 1
    return calls[0]


def _keyword_value(name: str) -> ast.AST:
    call = _execution_v2_call()

    values = {
        keyword.arg: keyword.value
        for keyword in call.keywords
        if keyword.arg is not None
    }

    assert name in values
    return values[name]


def test_safe003_missing_runtime_risk_authority_fails_closed():
    tree = ast.parse(
        SOURCE.read_text(encoding="utf-8")
    )

    defaults = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue

        if not any(
            isinstance(target, ast.Name)
            and target.id == "account_risk_approved"
            for target in node.targets
        ):
            continue

        if (
            isinstance(node.value, ast.Constant)
            and node.value.value is False
        ):
            defaults.append(node)

    assert len(defaults) == 1

    value = _keyword_value(
        "risk_approved"
    )

    assert isinstance(value, ast.Name)
    assert value.id == "account_risk_approved"



def test_safe003_runtime_risk_authority_is_not_static_allow():
    value = _keyword_value("risk_approved")

    assert not (
        isinstance(value, ast.Constant)
        and value.value is True
    )
