from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)
from backend.portfolio.portfolio_manager_v2 import (
    PortfolioManagerV2,
)


INTELLIGENCE_PATH = Path(
    "backend/api/routers/"
    "intelligence_decision_api_v3.py"
)

MARKET_PATH = Path(
    "backend/api/routers/market.py"
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(
        path.read_text(
            encoding="utf-8",
            errors="strict",
        ),
        filename=str(path),
    )


def _function(
    path: Path,
    name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = _tree(path)

    matches = [
        node
        for node in tree.body
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == name
        )
    ]

    assert len(matches) == 1, (
        f"Expected exactly one {name} "
        f"in {path}; found {len(matches)}"
    )

    return matches[0]


def _numeric_keyword_literals(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    keyword_name: str,
) -> list[tuple[int, str]]:
    records: list[tuple[int, str]] = []

    for node in ast.walk(function):
        if not isinstance(node, ast.keyword):
            continue

        if node.arg != keyword_name:
            continue

        value = node.value

        if (
            isinstance(value, ast.Constant)
            and isinstance(
                value.value,
                (int, float),
            )
            and not isinstance(
                value.value,
                bool,
            )
        ):
            records.append(
                (
                    node.lineno,
                    ast.unparse(value),
                )
            )

    return sorted(records)


def _service_analyze_calls(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.Call]:
    calls: list[ast.Call] = []

    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue

        try:
            name = ast.unparse(node.func)
        except Exception:
            continue

        if name == "service.analyze":
            calls.append(node)

    return sorted(
        calls,
        key=lambda node: node.lineno,
    )


def _keyword_value(
    call: ast.Call,
    keyword_name: str,
) -> str:
    values = [
        ast.unparse(keyword.value)
        for keyword in call.keywords
        if keyword.arg == keyword_name
    ]

    assert len(values) == 1, (
        f"Expected exactly one keyword "
        f"{keyword_name}; found {len(values)}"
    )

    return values[0]


def _call_texts(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    values: list[str] = []

    for node in ast.walk(function):
        if isinstance(node, ast.Call):
            try:
                values.append(
                    ast.unparse(node)
                )
            except Exception:
                continue

    return values


def test_active_account_profile_is_account_size_authority():
    manager = AccountConfigManagerV2()

    active = manager.get_active_account()

    assert (
        float(active.account_size)
        == pytest.approx(150000.0)
    )


def test_intelligence_runtime_has_no_literal_account_size():
    function = _function(
        INTELLIGENCE_PATH,
        "intelligence_decision_v3",
    )

    literals = _numeric_keyword_literals(
        function,
        "account_size",
    )

    assert literals == [], (
        "intelligence_decision_v3 still "
        "contains literal account_size "
        f"authority: {literals}"
    )


def test_market_webhook_has_no_literal_account_balance():
    function = _function(
        MARKET_PATH,
        "receive_market_webhook",
    )

    literals = _numeric_keyword_literals(
        function,
        "account_balance",
    )

    assert literals == [], (
        "receive_market_webhook still "
        "contains literal account_balance "
        f"authority: {literals}"
    )


def test_market_webhook_uses_portfolio_available_balance():
    function = _function(
        MARKET_PATH,
        "receive_market_webhook",
    )

    calls = _service_analyze_calls(function)

    assert len(calls) == 1

    account_balance_value = _keyword_value(
        calls[0],
        "account_balance",
    )

    call_texts = _call_texts(function)

    has_available_balance_resolution = any(
        "portfolio_manager_v2"
        in text
        and "get_available_balance"
        in text
        for text in call_texts
    )

    assert has_available_balance_resolution, (
        "receive_market_webhook must resolve "
        "automatic account balance from "
        "app.state.portfolio_manager_v2."
        "get_available_balance()"
    )

    assert (
        "available_balance"
        in account_balance_value
        or "account_balance"
        in account_balance_value
    ), (
        "service.analyze account_balance must "
        "consume the resolved runtime balance; "
        f"found {account_balance_value}"
    )


def test_manual_market_analysis_preserves_payload_balance():
    function = _function(
        MARKET_PATH,
        "analyze_live_market",
    )

    calls = _service_analyze_calls(function)

    assert len(calls) == 1

    assert (
        _keyword_value(
            calls[0],
            "account_balance",
        )
        == "payload.account_balance"
    )


def test_portfolio_available_balance_excludes_unrealized_pnl():
    portfolio = PortfolioManagerV2(
        starting_balance=10000.0,
    )

    portfolio.add_position(
        position={
            "position_id": "gap-3o-test",
            "symbol": "MNQ",
            "status": "OPEN",
            "direction": "LONG",
            "quantity": 1.0,
            "entry_price": 100.0,
            "current_price": 110.0,
            "stop_loss": 90.0,
            "take_profit": 120.0,
            "point_value": 2.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
        }
    )

    assert (
        portfolio.get_account_equity()
        == pytest.approx(10020.0)
    )

    assert (
        portfolio.get_available_balance()
        == pytest.approx(10000.0)
    )
