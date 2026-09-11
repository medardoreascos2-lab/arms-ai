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


def test_portfolio_manager_exposes_available_balance_authority():
    assert hasattr(
        PortfolioManagerV2,
        "get_available_balance",
    )


def test_execution_pipeline_does_not_construct_order_or_risk_context():
    function = _pipeline_function(_source())
    forbidden = {
        "signal", "order_type", "risk_context", "order_context",
        "current_price", "account_size", "account_balance", "risk_percent",
        "daily_pnl", "total_drawdown", "point_value",
    }
    for node in ast.walk(function):
        if isinstance(node, ast.keyword):
            assert node.arg not in forbidden
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant):
                    assert key.value not in forbidden
