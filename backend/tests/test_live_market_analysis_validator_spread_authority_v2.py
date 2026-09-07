from __future__ import annotations

import ast
from pathlib import Path


PRODUCTION_FILE = Path(
    "backend/services/live_market_analysis_service.py"
)


def _find_trade_validator_calls(
    tree: ast.AST,
) -> list[ast.Call]:
    calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        try:
            function_name = ast.unparse(node.func)
        except Exception:
            continue

        if (
            function_name
            == "self.trade_validator_v2.validate"
        ):
            calls.append(node)

    return calls


def _keyword_value(
    call: ast.Call,
    keyword_name: str,
) -> ast.expr:
    for keyword in call.keywords:
        if keyword.arg == keyword_name:
            return keyword.value

    raise AssertionError(
        f"{keyword_name} no fue suministrado "
        "a TradeValidatorV2.validate()."
    )


def test_trade_validator_spread_is_not_hardcoded() -> None:
    source = PRODUCTION_FILE.read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)

    calls = _find_trade_validator_calls(tree)

    assert len(calls) == 1, (
        "Se esperaba exactamente una llamada "
        "a TradeValidatorV2.validate()."
    )

    spread_expression = _keyword_value(
        calls[0],
        "spread_points",
    )

    assert not isinstance(
        spread_expression,
        ast.Constant,
    ), (
        "TradeValidatorV2 debe recibir spread "
        "desde una autoridad runtime; "
        "spread_points no puede ser un literal fijo."
    )


def test_trade_validator_spread_is_not_025_literal() -> None:
    source = PRODUCTION_FILE.read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)

    calls = _find_trade_validator_calls(tree)

    assert len(calls) == 1

    spread_expression = _keyword_value(
        calls[0],
        "spread_points",
    )

    rendered = ast.unparse(
        spread_expression
    ).replace(" ", "")

    assert rendered != "0.25", (
        "GAP #2K: el LiveMarketAnalysisService "
        "todavía suministra spread_points=0.25 "
        "al TradeValidatorV2."
    )
