from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from backend.account_risk.account_risk_guard import (
    AccountRiskGuard,
)


APP_PATH = Path("backend/api/app.py")
GUARD_PATH = Path(
    "backend/account_risk/account_risk_guard.py"
)


def _account_risk_guard_call() -> ast.Call:
    tree = ast.parse(
        APP_PATH.read_text(
            encoding="utf-8",
            errors="replace",
        )
    )

    calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        else:
            continue

        if name == "AccountRiskGuard":
            calls.append(node)

    assert len(calls) == 1
    return calls[0]


def _keyword_value(
    call: ast.Call,
    keyword: str,
) -> str | None:
    for item in call.keywords:
        if item.arg == keyword:
            return ast.unparse(item.value)

    return None


def _build_guard(
    daily_loss_limit: float | None,
) -> AccountRiskGuard:
    return AccountRiskGuard(
        daily_loss_limit=daily_loss_limit,
        max_trades_per_day=4,
        max_consecutive_losses=3,
        max_open_positions=1,
        max_risk_per_trade=250.0,
    )


def test_app_account_risk_guard_does_not_hardcode_daily_loss():
    call = _account_risk_guard_call()

    assert (
        _keyword_value(
            call,
            "daily_loss_limit",
        )
        != "3000.0"
    )


def test_app_account_risk_guard_consumes_resolved_daily_loss_authority():
    call = _account_risk_guard_call()

    assert (
        _keyword_value(
            call,
            "daily_loss_limit",
        )
        == "active_maximum_daily_loss"
    )


def test_guard_accepts_none_daily_loss_limit():
    guard = _build_guard(None)

    assert guard.daily_loss_limit is None


def test_guard_none_daily_loss_does_not_block():
    guard = _build_guard(None)

    result = guard.evaluate(
        trades_today=[
            {
                "pnl": -100000.0,
            }
        ],
        open_positions=0,
        proposed_risk=1.0,
    )

    assert result["approved"] is True

    assert (
        "daily_loss_limit"
        not in result["reasons"]
    )


@pytest.mark.parametrize(
    "daily_loss_limit",
    [
        1100.0,
        3000.0,
        4250.0,
    ],
)
def test_guard_blocks_at_resolved_numeric_daily_loss(
    daily_loss_limit: float,
):
    guard = _build_guard(
        daily_loss_limit
    )

    result = guard.evaluate(
        trades_today=[
            {
                "pnl": -daily_loss_limit,
            }
        ],
        open_positions=0,
        proposed_risk=1.0,
    )

    assert result["approved"] is False

    assert (
        "daily_loss_limit"
        in result["reasons"]
    )


def test_guard_daily_loss_contract_is_optional():
    signature = inspect.signature(
        AccountRiskGuard.__init__
    )

    parameter = signature.parameters[
        "daily_loss_limit"
    ]

    annotation = parameter.annotation

    assert (
        annotation
        is not inspect.Parameter.empty
    )

    annotation_text = str(annotation)

    assert (
        "None" in annotation_text
        or "Optional" in annotation_text
    )


def test_guard_none_semantics_are_explicit_in_source():
    source = GUARD_PATH.read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert (
        "self.daily_loss_limit is not None"
        in source
    )
