from __future__ import annotations

import ast
from pathlib import Path


PRODUCTION_FILE = Path(
    "backend/services/live_market_analysis_service.py"
)


def _source() -> str:
    return PRODUCTION_FILE.read_text(
        encoding="utf-8"
    )


def _tree() -> ast.Module:
    return ast.parse(_source())


def _live_class(
    tree: ast.Module,
) -> ast.ClassDef:
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "LiveMarketAnalysisService"
    ]

    assert len(classes) == 1

    return classes[0]


def _method(
    cls: ast.ClassDef,
    name: str,
) -> ast.FunctionDef:
    methods = [
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef)
        and node.name == name
    ]

    assert len(methods) == 1

    return methods[0]


def _validator_call(
    tree: ast.Module,
) -> ast.Call:
    calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        try:
            rendered = ast.unparse(node.func)
        except Exception:
            continue

        if (
            rendered
            == "self.trade_validator_v2.validate"
        ):
            calls.append(node)

    assert len(calls) == 1

    return calls[0]


def _keyword(
    call: ast.Call,
    name: str,
) -> ast.expr:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value

    raise AssertionError(
        f"{name} no fue suministrado."
    )


def test_live_service_accepts_runtime_spread_authority() -> None:
    tree = _tree()
    cls = _live_class(tree)
    init = _method(cls, "__init__")

    arguments = (
        [arg.arg for arg in init.args.posonlyargs]
        + [arg.arg for arg in init.args.args]
        + [arg.arg for arg in init.args.kwonlyargs]
    )

    assert (
        "runtime_spread_authority_v2"
        in arguments
    ), (
        "LiveMarketAnalysisService debe recibir "
        "RuntimeSpreadAuthorityV2 explícitamente."
    )


def test_live_service_stores_runtime_spread_authority() -> None:
    source = _source()

    assert (
        "self.runtime_spread_authority_v2"
        in source
    ), (
        "LiveMarketAnalysisService debe conservar "
        "la autoridad runtime de spread."
    )


def test_live_service_resolves_spread_from_runtime_authority() -> None:
    tree = _tree()
    cls = _live_class(tree)

    analyze_methods = [
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "analyze"
    ]

    assert len(analyze_methods) == 1

    analyze = analyze_methods[0]

    calls = []

    for node in ast.walk(analyze):
        if not isinstance(node, ast.Call):
            continue

        try:
            rendered = ast.unparse(node.func)
        except Exception:
            continue

        if rendered.endswith(
            ".get_spread_points"
        ):
            calls.append(node)

    assert len(calls) == 1, (
        "analyze() debe resolver exactamente una vez "
        "el spread mediante RuntimeSpreadAuthorityV2."
    )

    rendered = ast.unparse(
        calls[0].func
    )

    assert rendered == (
        "self.runtime_spread_authority_v2."
        "get_spread_points"
    )


def test_runtime_spread_resolution_is_symbol_scoped() -> None:
    tree = _tree()
    cls = _live_class(tree)
    analyze = _method(cls, "analyze")

    calls = [
        node
        for node in ast.walk(analyze)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get_spread_points"
    ]

    assert len(calls) == 1

    symbol_values = [
        keyword.value
        for keyword in calls[0].keywords
        if keyword.arg == "symbol"
    ]

    assert len(symbol_values) == 1

    assert ast.unparse(
        symbol_values[0]
    ) == "symbol"


def test_runtime_spread_resolution_receives_timezone_aware_now() -> None:
    tree = _tree()
    cls = _live_class(tree)
    analyze = _method(cls, "analyze")

    calls = [
        node
        for node in ast.walk(analyze)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get_spread_points"
    ]

    assert len(calls) == 1

    now_values = [
        keyword.value
        for keyword in calls[0].keywords
        if keyword.arg == "now"
    ]

    assert len(now_values) == 1

    rendered = ast.unparse(
        now_values[0]
    )

    assert (
        "datetime.now(timezone.utc)"
        in rendered
        or rendered
        in {
            "now",
            "current_time",
            "current_timestamp",
        }
    ), (
        "RuntimeSpreadAuthorityV2 debe recibir "
        "una referencia temporal runtime UTC."
    )


def test_trade_validator_uses_resolved_runtime_spread() -> None:
    tree = _tree()

    call = _validator_call(tree)

    spread_expression = _keyword(
        call,
        "spread_points",
    )

    assert not isinstance(
        spread_expression,
        ast.Constant,
    )

    rendered = ast.unparse(
        spread_expression
    )

    assert (
        "spread" in rendered.lower()
    ), (
        "TradeValidatorV2 debe consumir el spread "
        "resuelto por la autoridad runtime."
    )


def test_live_service_has_no_static_spread_fallback() -> None:
    tree = _tree()
    call = _validator_call(tree)

    spread_expression = _keyword(
        call,
        "spread_points",
    )

    rendered = ast.unparse(
        spread_expression
    ).replace(" ", "")

    assert rendered != "0.25"

    source = _source()

    forbidden = (
        "spread_points=0.25",
        "spread_points = 0.25",
    )

    for token in forbidden:
        assert token not in source
