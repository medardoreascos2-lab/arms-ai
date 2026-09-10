from __future__ import annotations

import ast
from pathlib import Path


MARKET_PATH = Path(
    "backend/api/routers/market.py"
)

PIPELINE_PATH = Path(
    "backend/api/routers/"
    "intelligence_decision_api_v3.py"
)

RESOLVER_NAME = (
    "_resolve_trade_management_point_value"
)


def _source(path: Path) -> str:
    return path.read_text(
        encoding="utf-8"
    )


def _tree(path: Path) -> ast.Module:
    return ast.parse(_source(path))


def _render(
    source: str,
    node: ast.AST,
) -> str:
    value = ast.get_source_segment(
        source,
        node,
    )

    assert value is not None

    return value


def _service_analyze_calls():
    source = _source(MARKET_PATH)
    tree = ast.parse(source)

    calls = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = _render(
            source,
            node.func,
        )

        if func != "service.analyze":
            continue

        keywords = {
            kw.arg: kw.value
            for kw in node.keywords
            if kw.arg is not None
        }

        calls.append(
            (
                node,
                keywords,
                source,
            )
        )

    return calls


def _automatic_call():
    matches = []

    for node, keywords, source in (
        _service_analyze_calls()
    ):
        required = {
            "symbol",
            "account_balance",
            "risk_percent",
            "point_value",
            "reward_risk_ratio",
        }

        if not required.issubset(
            keywords
        ):
            continue

        rendered = {
            key: _render(
                source,
                value,
            )
            for key, value
            in keywords.items()
            if key in required
        }

        if (
            rendered[
                "account_balance"
            ]
            == "available_balance"
            and rendered[
                "risk_percent"
            ]
            == "active_risk_percent"
        ):
            matches.append(
                (
                    node,
                    keywords,
                    source,
                    rendered,
                )
            )

    assert len(matches) == 1

    return matches[0]


def _manual_call():
    matches = []

    for node, keywords, source in (
        _service_analyze_calls()
    ):
        required = {
            "symbol",
            "account_balance",
            "risk_percent",
            "point_value",
            "reward_risk_ratio",
        }

        if not required.issubset(
            keywords
        ):
            continue

        rendered = {
            key: _render(
                source,
                value,
            )
            for key, value
            in keywords.items()
            if key in required
        }

        if (
            rendered[
                "account_balance"
            ]
            == "payload.account_balance"
        ):
            matches.append(
                rendered
            )

    assert len(matches) == 1

    return matches[0]


def _pipeline_point_value() -> str:
    source = _source(
        PIPELINE_PATH
    )
    tree = ast.parse(source)

    fn = next(
        node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        and node.name
        == "execution_pipeline_v3"
    )

    values = []

    for node in ast.walk(fn):
        if not isinstance(
            node,
            ast.Dict,
        ):
            continue

        for key, value in zip(
            node.keys,
            node.values,
        ):
            if (
                isinstance(
                    key,
                    ast.Constant,
                )
                and key.value
                == "point_value"
            ):
                values.append(
                    _render(
                        source,
                        value,
                    )
                )

    assert len(values) == 1

    return values[0]


def test_market_auto_has_no_literal_point_value_2_0():
    _, _, _, rendered = (
        _automatic_call()
    )

    assert (
        rendered["point_value"]
        != "2.0"
    )


def test_market_auto_uses_existing_point_value_resolver():
    _, keywords, source, _ = (
        _automatic_call()
    )

    point_value = keywords[
        "point_value"
    ]

    assert isinstance(
        point_value,
        ast.Call,
    )

    assert (
        _render(
            source,
            point_value.func,
        )
        == RESOLVER_NAME
    )

    assert len(
        point_value.args
    ) == 1

    argument = point_value.args[0]

    assert isinstance(
        argument,
        ast.Attribute,
    )

    assert isinstance(
        argument.value,
        ast.Name,
    )

    assert (
        argument.value.id
        == "candle"
    )

    assert (
        argument.attr
        == "symbol"
    )


def test_market_auto_point_value_resolver_uses_candle_symbol():
    _, _, _, rendered = (
        _automatic_call()
    )

    assert (
        rendered["symbol"]
        == "candle.symbol"
    )


def test_market_manual_point_value_remains_payload():
    rendered = _manual_call()

    assert (
        rendered["point_value"]
        == "payload.point_value"
    )


def test_market_auto_account_balance_remains_available_balance():
    _, _, _, rendered = (
        _automatic_call()
    )

    assert (
        rendered["account_balance"]
        == "available_balance"
    )


def test_market_auto_risk_percent_remains_active_risk_percent():
    _, _, _, rendered = (
        _automatic_call()
    )

    assert (
        rendered["risk_percent"]
        == "active_risk_percent"
    )


def test_market_auto_reward_risk_ratio_remains_2_0():
    _, _, _, rendered = (
        _automatic_call()
    )

    assert (
        rendered[
            "reward_risk_ratio"
        ]
        == "2.0"
    )


def test_execution_pipeline_point_value_remains_20():
    assert (
        _pipeline_point_value()
        == "20"
    )
