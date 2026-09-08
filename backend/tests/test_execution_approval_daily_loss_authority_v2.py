from __future__ import annotations

import ast
from pathlib import Path


ENGINE_PATH = Path(
    "backend/execution/execution_approval_engine.py"
)

ROUTER_PATH = Path(
    "backend/api/routers/execution_approval_api_v2.py"
)


def _parse(path: Path) -> tuple[str, ast.Module]:
    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )
    return source, ast.parse(source)


def _validate_execution_function(
    tree: ast.Module,
) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "validate_execution"
        ):
            return node

    raise AssertionError(
        "validate_execution not found"
    )


def _default_for_argument(
    function: ast.FunctionDef,
    argument_name: str,
) -> ast.expr | None:
    positional = (
        list(function.args.posonlyargs)
        + list(function.args.args)
    )

    defaults = list(function.args.defaults)

    if defaults:
        args_with_defaults = positional[
            -len(defaults):
        ]

        for arg, default in zip(
            args_with_defaults,
            defaults,
        ):
            if arg.arg == argument_name:
                return default

    for arg, default in zip(
        function.args.kwonlyargs,
        function.args.kw_defaults,
    ):
        if arg.arg == argument_name:
            return default

    return None


def test_execution_approval_engine_has_no_literal_daily_loss_authority():
    source, tree = _parse(ENGINE_PATH)

    function = _validate_execution_function(
        tree
    )

    default = _default_for_argument(
        function,
        "daily_loss_limit",
    )

    if default is None:
        return

    rendered = ast.get_source_segment(
        source,
        default,
    )

    assert rendered != "3000"


def test_production_router_does_not_silently_use_engine_daily_loss_default():
    source, tree = _parse(ROUTER_PATH)

    calls = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Call)
            and isinstance(
                node.func,
                ast.Attribute,
            )
            and node.func.attr
            == "validate_execution"
        )
    ]

    assert len(calls) == 1

    call = calls[0]

    keyword_names = {
        keyword.arg
        for keyword in call.keywords
        if keyword.arg is not None
    }

    assert "daily_loss_limit" in keyword_names


def test_router_daily_loss_limit_is_not_literal_policy():
    source, tree = _parse(ROUTER_PATH)

    calls = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Call)
            and isinstance(
                node.func,
                ast.Attribute,
            )
            and node.func.attr
            == "validate_execution"
        )
    ]

    assert len(calls) == 1

    call = calls[0]

    daily_loss_keywords = [
        keyword
        for keyword in call.keywords
        if keyword.arg == "daily_loss_limit"
    ]

    assert len(daily_loss_keywords) == 1

    expression = daily_loss_keywords[0].value

    assert not isinstance(
        expression,
        ast.Constant,
    ), (
        "daily_loss_limit must come from "
        "runtime/canonical authority, not "
        "a router literal"
    )


def test_router_does_not_introduce_literal_3000_daily_loss_policy():
    source = ROUTER_PATH.read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "daily_loss_limit=3000" not in (
        source.replace(" ", "")
    )
