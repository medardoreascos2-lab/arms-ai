from __future__ import annotations

import ast
from pathlib import Path

from backend.portfolio.portfolio_manager_v2 import (
    PortfolioManagerV2,
)


ROUTER_PATH = Path(
    "backend/api/routers/"
    "intelligence_decision_api_v3.py"
)


def _source() -> str:
    return ROUTER_PATH.read_text(
        encoding="utf-8"
    )


def _pipeline_function(
    source: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)

    for node in tree.body:
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == "execution_pipeline_v3"
        ):
            return node

    raise AssertionError(
        "execution_pipeline_v3 no existe."
    )


def _risk_context_values() -> dict[str, ast.AST]:
    source = _source()
    function = _pipeline_function(source)

    expected_keys = {
        "current_price",
        "account_size",
        "account_balance",
        "risk_percent",
        "daily_pnl",
        "total_drawdown",
    }

    for node in ast.walk(function):
        if not isinstance(node, ast.Dict):
            continue

        values: dict[str, ast.AST] = {}

        for key, value in zip(
            node.keys,
            node.values,
        ):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
            ):
                values[key.value] = value

        if expected_keys.issubset(values):
            return values

    raise AssertionError(
        "risk_context no fue encontrado."
    )


def _render(node: ast.AST) -> str:
    rendered = ast.get_source_segment(
        _source(),
        node,
    )

    assert rendered is not None
    return rendered.strip()


def test_portfolio_manager_exposes_available_balance_authority():
    assert hasattr(
        PortfolioManagerV2,
        "get_available_balance",
    )


def test_execution_pipeline_has_no_literal_account_balance():
    node = _risk_context_values()[
        "account_balance"
    ]

    assert not isinstance(
        node,
        ast.Constant,
    ), (
        "execution_pipeline_v3 contiene "
        "literal account_balance authority: "
        f"{_render(node)}"
    )


def test_execution_pipeline_uses_portfolio_available_balance():
    source = _source()
    node = _risk_context_values()[
        "account_balance"
    ]
    rendered = _render(node)

    assert (
        "portfolio_manager_v2"
        in source
    ), (
        "execution_pipeline_v3 debe usar "
        "portfolio_manager_v2."
    )

    assert (
        "get_available_balance"
        in source
    ), (
        "execution_pipeline_v3 debe resolver "
        "account_balance mediante "
        "get_available_balance()."
    )

    assert (
        "available_balance" in rendered
        or "get_available_balance" in rendered
    ), (
        "risk_context.account_balance debe "
        "usar el balance disponible resuelto; "
        f"actual={rendered}"
    )


def test_gap_3q_preserves_account_size_authority():
    node = _risk_context_values()[
        "account_size"
    ]

    assert _render(node) == (
        "active_account_size"
    )


def test_gap_3q_does_not_expand_to_point_value():
    values = _risk_context_values()

    # GAP #3U owns point-value authority at the lifecycle
    # boundary. The execution-pipeline router must not
    # provide point_value inside risk_context.
    assert "point_value" not in values


def test_gap_3q_preserves_remaining_runtime_fields():
    values = _risk_context_values()

    assert _render(
        values["risk_percent"]
    ) == "active_risk_percent"

    assert _render(
        values["daily_pnl"]
    ) == 'request.app.state\n                    .account_state_manager_v2\n                    .get_state()["daily_pnl"]'

    assert _render(
        values["total_drawdown"]
    ) == "0"
