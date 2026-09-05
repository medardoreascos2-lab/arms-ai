from __future__ import annotations

import ast
from pathlib import Path


LIVE_PATH = Path(
    "backend/services/live_market_analysis_service.py"
)


def _tree() -> ast.AST:
    return ast.parse(
        LIVE_PATH.read_text(
            encoding="utf-8",
        )
    )


def _validator_has_open_position_expression() -> str:
    values: list[str] = []

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "validate"
            and isinstance(
                func.value,
                ast.Attribute,
            )
            and func.value.attr
            == "trade_validator_v2"
        ):
            continue

        for keyword in node.keywords:
            if keyword.arg == "has_open_position":
                values.append(
                    ast.unparse(
                        keyword.value
                    )
                )

    assert len(values) == 1

    return values[0]


def _position_authority_calls() -> list[ast.Call]:
    calls: list[ast.Call] = []

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if (
            isinstance(func, ast.Attribute)
            and func.attr == "get_open_position"
        ):
            calls.append(node)

    return calls


def _validator_call() -> ast.Call:
    calls: list[ast.Call] = []

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if (
            isinstance(func, ast.Attribute)
            and func.attr == "validate"
            and isinstance(
                func.value,
                ast.Attribute,
            )
            and func.value.attr
            == "trade_validator_v2"
        ):
            calls.append(node)

    assert len(calls) == 1

    return calls[0]


def test_validator_has_open_position_is_not_static_false():
    expression = (
        _validator_has_open_position_expression()
    )

    assert expression != "False"


def test_validator_has_open_position_uses_runtime_position_authority():
    expression = (
        _validator_has_open_position_expression()
    )

    assert (
        "open_position" in expression
        or "open_positions" in expression
    )


def test_position_authority_is_symbol_and_timeframe_aware():
    calls = _position_authority_calls()

    assert len(calls) == 1

    rendered = ast.unparse(
        calls[0]
    )

    assert "symbol=symbol" in rendered
    assert "timeframe=timeframe" in rendered


def test_position_authority_is_resolved_before_validator():
    position_calls = (
        _position_authority_calls()
    )

    assert len(position_calls) == 1

    validator_call = _validator_call()

    assert (
        position_calls[0].lineno
        < validator_call.lineno
    )
