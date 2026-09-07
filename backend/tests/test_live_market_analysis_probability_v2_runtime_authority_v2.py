from __future__ import annotations

import ast
from pathlib import Path


LIVE_FILE = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "live_market_analysis_service.py"
)


def _probability_v2_call() -> ast.Call:
    source = LIVE_FILE.read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)

    calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        try:
            name = ast.unparse(node.func)
        except Exception:
            continue

        if (
            name
            == "self.probability_engine_v2.evaluate"
        ):
            calls.append(node)

    assert len(calls) == 1

    return calls[0]


def _value(argument: str) -> str:
    call = _probability_v2_call()

    values = {
        keyword.arg: ast.unparse(
            keyword.value
        )
        for keyword in call.keywords
        if keyword.arg is not None
    }

    assert argument in values

    return values[argument]


def test_probability_v2_uses_runtime_risk_authority():
    value = _value("risk_approved")

    assert "account_risk_approved" in value
    assert "locals()" in value
    assert "else True" in value


def test_probability_v2_uses_runtime_sizing_authority():
    value = _value("sizing_approved")

    assert "position_sizing_approved" in value
    assert "locals()" in value
    assert "else True" in value


def test_probability_v2_does_not_receive_static_risk_allow():
    assert _value("risk_approved") != "True"


def test_probability_v2_does_not_receive_static_sizing_allow():
    assert _value("sizing_approved") != "True"


def test_probability_v2_runtime_authority_sources_are_exact():
    assert _value(
        "risk_approved"
    ) == (
        "account_risk_approved "
        "if 'account_risk_approved' in locals() "
        "else True"
    )

    assert _value(
        "sizing_approved"
    ) == (
        "position_sizing_approved "
        "if 'position_sizing_approved' in locals() "
        "else True"
    )
