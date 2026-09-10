from __future__ import annotations

import ast
from pathlib import Path


ROUTER = Path(
    "backend/api/routers/"
    "intelligence_decision_api_v3.py"
)

EXPECTED_TOTAL_DRAWDOWN_SOURCE = (
    "request.app.state\n"
    "                    "
    ".account_state_manager_v2\n"
    "                    "
    '.get_state()["drawdown"]'
)


def _source() -> str:
    return ROUTER.read_text(
        encoding="utf-8",
        errors="replace",
    )


def _tree() -> ast.AST:
    return ast.parse(_source())


def _risk_context_values() -> dict[str, str]:
    source = _source()
    tree = ast.parse(source)

    candidates: list[dict[str, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue

        rendered: dict[str, str] = {}

        for key, value in zip(
            node.keys,
            node.values,
        ):
            if not (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
            ):
                continue

            segment = ast.get_source_segment(
                source,
                value,
            )

            if segment is not None:
                rendered[key.value] = segment

        if (
            "account_size" in rendered
            and "account_balance" in rendered
            and "risk_percent" in rendered
            and "daily_pnl" in rendered
            and "total_drawdown" in rendered
        ):
            candidates.append(rendered)

    assert len(candidates) == 1

    return candidates[0]


def test_gap_3w_router_has_single_total_drawdown_field():
    values = _risk_context_values()

    assert "total_drawdown" in values


def test_gap_3w_rejects_literal_zero_total_drawdown():
    values = _risk_context_values()

    assert values["total_drawdown"] != "0"


def test_gap_3w_reads_total_drawdown_from_runtime_account_state():
    values = _risk_context_values()

    assert (
        values["total_drawdown"]
        == EXPECTED_TOTAL_DRAWDOWN_SOURCE
    )


def test_gap_3w_uses_account_state_manager_v2():
    values = _risk_context_values()

    assert (
        "account_state_manager_v2"
        in values["total_drawdown"]
    )


def test_gap_3w_reads_drawdown_field():
    values = _risk_context_values()

    assert (
        '.get_state()["drawdown"]'
        in values["total_drawdown"]
    )


def test_gap_3w_preserves_existing_runtime_authorities():
    values = _risk_context_values()

    assert (
        "active_account_size"
        in values["account_size"]
    )

    assert (
        "available_balance"
        in values["account_balance"]
    )

    assert (
        "active_risk_percent"
        in values["risk_percent"]
    )

    assert (
        "account_state_manager_v2"
        in values["daily_pnl"]
    )

    assert (
        '.get_state()["daily_pnl"]'
        in values["daily_pnl"]
    )
