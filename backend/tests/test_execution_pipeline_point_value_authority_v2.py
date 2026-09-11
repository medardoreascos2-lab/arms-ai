from __future__ import annotations

import ast
from pathlib import Path


ROUTER_PATH = Path(
    "backend/api/routers/"
    "intelligence_decision_api_v3.py"
)

LIFECYCLE_PATH = Path(
    "backend/services/"
    "trade_lifecycle_service_v2.py"
)


def _source(path: Path) -> str:
    return path.read_text(
        encoding="utf-8"
    )


def _function(
    path: Path,
    name: str,
) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]:
    source = _source(path)
    tree = ast.parse(source)

    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        and node.name == name
    ]

    assert len(matches) == 1

    return matches[0], source


def _execution_pipeline() -> tuple[
    ast.FunctionDef | ast.AsyncFunctionDef,
    str,
]:
    return _function(
        ROUTER_PATH,
        "execution_pipeline_v3",
    )


def _submit_signal() -> tuple[
    ast.FunctionDef | ast.AsyncFunctionDef,
    str,
]:
    return _function(
        LIFECYCLE_PATH,
        "submit_signal",
    )


def _render(
    source: str,
    node: ast.AST,
) -> str:
    rendered = ast.get_source_segment(
        source,
        node,
    )

    assert rendered is not None

    return rendered








def test_execution_pipeline_does_not_supply_point_value():
    function, source = _execution_pipeline()
    assert "point_value" not in _render(source, function)


def test_execution_pipeline_does_not_resolve_instruments_for_execution():
    function, source = _execution_pipeline()
    assert "get_profile" not in _render(source, function)


def test_submit_signal_owns_instrument_profile_resolution():
    function, source = (
        _submit_signal()
    )

    profile_calls = []

    for node in ast.walk(function):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        func = node.func

        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "get_profile"
        ):
            continue

        rendered_func = _render(
            source,
            func,
        )

        if (
            "instrument_profile_engine"
            in rendered_func
        ):
            profile_calls.append(node)

    assert len(profile_calls) == 1


def test_submit_signal_overrides_risk_context_point_value():
    function, source = (
        _submit_signal()
    )

    assignments = []

    for node in ast.walk(function):
        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        for target in node.targets:
            if not isinstance(
                target,
                ast.Subscript,
            ):
                continue

            rendered_target = _render(
                source,
                target,
            )

            if (
                "risk_context"
                in rendered_target
                and "point_value"
                in rendered_target
            ):
                assignments.append(
                    (
                        rendered_target,
                        _render(
                            source,
                            node.value,
                        ),
                    )
                )

    assert len(assignments) == 1

    target, value = assignments[0]

    assert "risk_context" in target
    assert "point_value" in target
    assert value == "resolved_point_value"


def test_point_value_authority_is_symbol_derived():
    function, source = (
        _submit_signal()
    )

    profile_call = next(
        (
            node
            for node in ast.walk(
                function
            )
            if isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Attribute,
            )
            and node.func.attr
            == "get_profile"
        ),
        None,
    )

    assert profile_call is not None

    symbol_keyword = next(
        (
            keyword
            for keyword
            in profile_call.keywords
            if keyword.arg == "symbol"
        ),
        None,
    )

    assert symbol_keyword is not None

    assert (
        _render(
            source,
            symbol_keyword.value,
        )
        == "normalized_symbol"
    )


def test_execution_pipeline_does_not_submit_a_signal_or_execution_context():
    function, source = _execution_pipeline()
    rendered = _render(source, function)
    for command in ("submit_signal", "risk_context", "order_context", "prepare_order"):
        assert command not in rendered
