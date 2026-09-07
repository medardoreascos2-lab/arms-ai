from __future__ import annotations

import ast
from pathlib import Path

from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)
from backend.risk.multi_account_risk_engine_v2 import (
    MultiAccountRiskEngineV2,
)


APP_PATH = Path("backend/api/app.py")


def _create_app_node() -> ast.FunctionDef:
    tree = ast.parse(
        APP_PATH.read_text(encoding="utf-8")
    )

    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "create_app"
        ):
            return node

    raise AssertionError("create_app no encontrado")


def _account_risk_guard_call() -> ast.Call:
    create_app = _create_app_node()

    calls = [
        node
        for node in ast.walk(create_app)
        if (
            isinstance(node, ast.Call)
            and (
                (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "AccountRiskGuard"
                )
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "AccountRiskGuard"
                )
            )
        )
    ]

    assert len(calls) == 1
    return calls[0]


def _keyword_value(
    call: ast.Call,
    keyword_name: str,
) -> ast.expr:
    for keyword in call.keywords:
        if keyword.arg == keyword_name:
            return keyword.value

    raise AssertionError(
        f"keyword ausente: {keyword_name}"
    )


def test_active_profile_defines_risk_per_trade_authority():
    account_manager = AccountConfigManagerV2()

    engine = MultiAccountRiskEngineV2(
        account_manager=account_manager
    )

    profile = engine.get_active_risk_profile()

    assert profile["account"] == "TOPSTEP_150K"
    assert profile["account_size"] == 150000
    assert profile["risk_percent"] == 0.5
    assert profile["risk_per_trade"] == 750.0


def test_app_guard_does_not_hardcode_max_risk_per_trade():
    call = _account_risk_guard_call()

    value = _keyword_value(
        call,
        "max_risk_per_trade",
    )

    assert not (
        isinstance(value, ast.Constant)
        and isinstance(value.value, (int, float))
    )


def test_app_guard_uses_resolved_active_max_risk():
    call = _account_risk_guard_call()

    value = _keyword_value(
        call,
        "max_risk_per_trade",
    )

    assert isinstance(value, ast.Name)

    assert value.id == "active_max_risk_per_trade"


def test_active_max_risk_is_resolved_before_guard():
    create_app = _create_app_node()

    assignments = []

    guard_lines = []

    for node in ast.walk(create_app):
        if isinstance(
            node,
            (ast.Assign, ast.AnnAssign),
        ):
            targets = []

            if isinstance(node, ast.Assign):
                targets = node.targets
            elif node.target is not None:
                targets = [node.target]

            for target in targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id
                    == "active_max_risk_per_trade"
                ):
                    assignments.append(node.lineno)

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "AccountRiskGuard"
        ):
            guard_lines.append(node.lineno)

    assert len(assignments) == 1
    assert len(guard_lines) == 1

    assert assignments[0] < guard_lines[0]


def test_active_max_risk_source_is_active_account_policy():
    create_app = _create_app_node()

    source = ast.get_source_segment(
        APP_PATH.read_text(encoding="utf-8"),
        create_app,
    )

    assert source is not None

    assert "active_max_risk_per_trade" in source

    assert (
        "active_account_profile"
        in source
        or "MultiAccountRiskEngineV2"
        in source
    )


def test_guard_local_constructor_contract_remains_configurable():
    from backend.account_risk.account_risk_guard import (
        AccountRiskGuard,
    )

    guard = AccountRiskGuard(
        daily_loss_limit=None,
        max_trades_per_day=4,
        max_consecutive_losses=3,
        max_open_positions=1,
        max_risk_per_trade=50.0,
    )

    blocked = guard.evaluate(
        trades_today=[],
        open_positions=0,
        proposed_risk=51.0,
    )

    allowed = guard.evaluate(
        trades_today=[],
        open_positions=0,
        proposed_risk=50.0,
    )

    assert blocked["approved"] is False
    assert "max_risk_per_trade" in blocked["reasons"]

    assert allowed["approved"] is True
