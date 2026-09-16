from __future__ import annotations

import ast
from pathlib import Path


SOURCE = Path(
    "backend/services/live_market_analysis_service.py"
)


def _tree() -> ast.Module:
    return ast.parse(
        SOURCE.read_text(encoding="utf-8")
    )


def _calls(
    function_text: str,
) -> list[ast.Call]:
    found: list[ast.Call] = []

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue

        if ast.unparse(node.func) == function_text:
            found.append(node)

    return sorted(
        found,
        key=lambda node: node.lineno,
    )


def _keyword(
    call: ast.Call,
    name: str,
) -> ast.AST:
    values = {
        keyword.arg: keyword.value
        for keyword in call.keywords
    }

    assert name in values

    return values[name]


def test_safe003_final_confluence_uses_resolved_risk_authority():
    calls = _calls(
        "self._evaluate_confluence_v2"
    )

    assert len(calls) == 2

    early, final = calls

    # The early analytical confluence is intentionally
    # pre-runtime-authority and is covered separately.
    assert early.lineno < final.lineno

    risk_value = _keyword(
        final,
        "risk_approved",
    )

    assert isinstance(
        risk_value,
        ast.Name,
    )

    assert (
        risk_value.id
        == "account_risk_approved"
    )


def test_safe003_probability_uses_resolved_risk_authority():
    calls = _calls(
        "self.probability_engine_v2.evaluate"
    )

    assert len(calls) == 1

    risk_value = _keyword(
        calls[0],
        "risk_approved",
    )

    assert isinstance(
        risk_value,
        ast.Name,
    )

    assert (
        risk_value.id
        == "account_risk_approved"
    )


def test_safe003_final_paths_have_no_locals_risk_fallback():
    calls = []

    calls.extend(
        _calls(
            "self._evaluate_confluence_v2"
        )[1:]
    )

    calls.extend(
        _calls(
            "self.probability_engine_v2.evaluate"
        )
    )

    violations: list[str] = []

    for call in calls:
        value = _keyword(
            call,
            "risk_approved",
        )

        text = ast.unparse(value)

        if (
            "locals()" in text
            or "else True" in text
        ):
            violations.append(
                f"{call.lineno}:{text}"
            )

    assert violations == []
