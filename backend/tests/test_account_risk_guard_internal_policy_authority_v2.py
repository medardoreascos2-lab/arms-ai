import ast
from pathlib import Path

import pytest

from backend.config_settings import ArmsSettings


APP_PATH = Path("backend/api/app.py")
SETTINGS_PATH = Path("backend/config_settings.py")


def _source(path: Path) -> str:
    return path.read_text(
        encoding="utf-8",
        errors="strict",
    )


def _create_app_node() -> ast.FunctionDef:
    tree = ast.parse(_source(APP_PATH))

    matches = [
        node
        for node in tree.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
        and node.name == "create_app"
    ]

    assert len(matches) == 1

    return matches[0]


def _account_risk_guard_call() -> ast.Call:
    create_app = _create_app_node()

    calls = [
        node
        for node in ast.walk(create_app)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "AccountRiskGuard"
    ]

    assert len(calls) == 1

    return calls[0]


def _keyword_expression(name: str) -> ast.AST:
    call = _account_risk_guard_call()

    matches = [
        keyword.value
        for keyword in call.keywords
        if keyword.arg == name
    ]

    assert len(matches) == 1

    return matches[0]


def _attribute_chain(node: ast.AST) -> list[str]:
    parts: list[str] = []

    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value

    if isinstance(node, ast.Name):
        parts.append(node.id)

    return list(reversed(parts))


def test_arms_settings_owns_internal_account_risk_discipline_policy():
    settings = ArmsSettings()

    assert hasattr(
        settings,
        "internal_max_trades_per_day",
    )
    assert hasattr(
        settings,
        "internal_max_consecutive_losses",
    )

    assert (
        settings.internal_max_trades_per_day
        == 4
    )
    assert (
        settings.internal_max_consecutive_losses
        == 3
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("internal_max_trades_per_day", 0),
        ("internal_max_trades_per_day", -1),
        ("internal_max_consecutive_losses", 0),
        ("internal_max_consecutive_losses", -1),
    ],
)
def test_internal_account_risk_discipline_policy_must_be_positive(
    field,
    value,
):
    with pytest.raises(ValueError, match=field):
        ArmsSettings(
            **{
                field: value,
            }
        )


def test_create_app_consumes_runtime_context_max_trades_authority():
    expression = _keyword_expression(
        "max_trades_per_day"
    )

    assert not (
        isinstance(expression, ast.Constant)
        and expression.value == 4
    )

    assert _attribute_chain(expression) == [
        "internal_policy_settings",
        "internal_max_trades_per_day",
    ]


def test_create_app_consumes_runtime_context_consecutive_losses_authority():
    expression = _keyword_expression(
        "max_consecutive_losses"
    )

    assert not (
        isinstance(expression, ast.Constant)
        and expression.value == 3
    )

    assert _attribute_chain(expression) == [
        "internal_policy_settings",
        "internal_max_consecutive_losses",
    ]


def test_settings_source_defines_both_internal_policy_fields():
    source = _source(SETTINGS_PATH)

    assert (
        "internal_max_trades_per_day"
        in source
    )
    assert (
        "internal_max_consecutive_losses"
        in source
    )
