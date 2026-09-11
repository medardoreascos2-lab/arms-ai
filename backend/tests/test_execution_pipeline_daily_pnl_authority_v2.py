from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

ROUTER_PATH = (
    ROOT
    / "backend"
    / "api"
    / "routers"
    / "intelligence_decision_api_v3.py"
)

ACCOUNT_STATE_PATH = (
    ROOT
    / "backend"
    / "account"
    / "account_state_manager_v2.py"
)

APP_PATH = (
    ROOT
    / "backend"
    / "api"
    / "app.py"
)


def _source(path: Path) -> str:
    return path.read_text(
        encoding="utf-8",
    )


def _execution_pipeline_node():
    source = _source(ROUTER_PATH)
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
        and node.name
        == "execution_pipeline_v3"
    ]

    assert len(matches) == 1

    return source, matches[0]


def _dict_values_for_key(
    source: str,
    root: ast.AST,
    key_name: str,
) -> list[ast.AST]:
    values: list[ast.AST] = []

    for node in ast.walk(root):
        if not isinstance(node, ast.Dict):
            continue

        for key, value in zip(
            node.keys,
            node.values,
        ):
            if (
                isinstance(key, ast.Constant)
                and key.value == key_name
            ):
                values.append(value)

    return values


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


def test_gap_3v_account_state_manager_owns_daily_pnl():
    source = _source(
        ACCOUNT_STATE_PATH,
    )

    assert '"daily_pnl": 0.0' in source
    assert "def record_daily_pnl(" in source
    assert "def reset_daily_state(" in source


def test_gap_3v_account_state_exposes_daily_pnl():
    source = _source(
        ACCOUNT_STATE_PATH,
    )

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
        and node.name == "get_state"
    ]

    assert len(matches) == 1

    rendered = _render(
        source,
        matches[0],
    )

    assert "self._state" in rendered


def test_gap_3v_runtime_exposes_account_state_manager():
    source = _source(APP_PATH)

    assert (
        "app.state.account_state_manager_v2"
        in source
    )


def test_execution_pipeline_does_not_encode_daily_pnl_zero():
    source, pipeline = (
        _execution_pipeline_node()
    )

    values = _dict_values_for_key(
        source,
        pipeline,
        "daily_pnl",
    )

    rendered = [
        _render(
            source,
            value,
        )
        for value in values
    ]

    assert "0" not in rendered


def test_execution_pipeline_does_not_require_account_state_to_read_activity():
    source, pipeline = _execution_pipeline_node()
    assert "account_state_manager_v2" not in _render(source, pipeline)
    assert _dict_values_for_key(source, pipeline, "daily_pnl") == []


def test_execution_pipeline_does_not_build_signal_evidence():
    source, pipeline = _execution_pipeline_node()
    for field in ("current_price", "total_drawdown", "probability", "confluence_score"):
        assert _dict_values_for_key(source, pipeline, field) == []
