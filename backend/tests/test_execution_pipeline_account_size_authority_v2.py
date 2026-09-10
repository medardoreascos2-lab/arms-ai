import ast
from pathlib import Path

from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)


ROUTER_PATH = Path(
    "backend/api/routers/"
    "intelligence_decision_api_v3.py"
)


def _execution_pipeline_node():
    source = ROUTER_PATH.read_text(
        encoding="utf-8",
    )
    tree = ast.parse(source)

    matches = [
        node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        and node.name == "execution_pipeline_v3"
    ]

    assert len(matches) == 1

    return source, matches[0]


def _dict_values_for_key(
    node: ast.AST,
    key_name: str,
):
    values = []

    for candidate in ast.walk(node):
        if not isinstance(candidate, ast.Dict):
            continue

        for key, value in zip(
            candidate.keys,
            candidate.values,
        ):
            if (
                isinstance(key, ast.Constant)
                and key.value == key_name
            ):
                values.append(value)

    return values


def _numeric_literals(
    values,
):
    records = []

    for value in values:
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
                    value.lineno,
                    value.value,
                )
            )

    return records


def _render(
    source: str,
    node: ast.AST,
) -> str:
    return (
        ast.get_source_segment(
            source,
            node,
        )
        or ""
    )


def test_active_account_profile_is_execution_pipeline_account_size_authority():
    manager = AccountConfigManagerV2()

    active = manager.get_active_account()

    assert float(active.account_size) > 0.0


def test_execution_pipeline_has_no_literal_account_size():
    _, pipeline = _execution_pipeline_node()

    values = _dict_values_for_key(
        pipeline,
        "account_size",
    )

    literals = _numeric_literals(values)

    assert literals == [], (
        "execution_pipeline_v3 contains "
        "literal account_size authority: "
        f"{literals}"
    )


def test_execution_pipeline_uses_active_account_size():
    source, pipeline = _execution_pipeline_node()

    values = _dict_values_for_key(
        pipeline,
        "account_size",
    )

    assert len(values) == 1

    rendered_value = _render(
        source,
        values[0],
    )

    pipeline_source = _render(
        source,
        pipeline,
    )

    assert (
        "get_active_account()"
        in pipeline_source
    )

    assert (
        ".account_size"
        in pipeline_source
    )

    assert (
        "active_account_size"
        in rendered_value
        or "account_size"
        in rendered_value
    ), (
        "execution_pipeline_v3 account_size "
        "must resolve from active account "
        "authority; found "
        f"{rendered_value}"
    )


def test_execution_pipeline_risk_percent_authority_is_preserved():
    source, pipeline = _execution_pipeline_node()

    values = _dict_values_for_key(
        pipeline,
        "risk_percent",
    )

    assert len(values) == 1

    rendered_value = _render(
        source,
        values[0],
    )

    assert (
        "active_risk_percent"
        in rendered_value
        or "risk_percent"
        in rendered_value
    )


def test_gap_3p_does_not_expand_to_account_balance():
    source, pipeline = _execution_pipeline_node()

    values = _dict_values_for_key(
        pipeline,
        "account_balance",
    )

    assert len(values) == 1

    rendered_value = _render(
        source,
        values[0],
    )

    assert rendered_value == "150000"


def test_gap_3p_does_not_expand_to_point_value():
    source, pipeline = _execution_pipeline_node()

    values = _dict_values_for_key(
        pipeline,
        "point_value",
    )

    assert len(values) == 1

    rendered_value = _render(
        source,
        values[0],
    )

    assert rendered_value == "20"
