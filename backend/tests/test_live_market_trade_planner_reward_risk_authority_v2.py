from __future__ import annotations

import ast
from pathlib import Path


SERVICE_PATH = Path(
    "backend/services/"
    "live_market_analysis_service.py"
)

PLANNER_PATH = Path(
    "backend/execution/"
    "trade_planner_v2.py"
)

MARKET_PATH = Path(
    "backend/api/routers/market.py"
)

APPROVAL_PATH = Path(
    "backend/api/routers/"
    "execution_approval_api_v2.py"
)

PIPELINE_PATH = Path(
    "backend/api/routers/"
    "intelligence_decision_api_v3.py"
)


def _source(path: Path) -> str:
    return path.read_text(
        encoding="utf-8"
    )


def _tree(path: Path) -> ast.Module:
    return ast.parse(
        _source(path)
    )


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


def _service_analyze_function():
    tree = _tree(
        SERVICE_PATH
    )

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
        and node.name == "analyze"
    ]

    assert len(matches) == 1

    return matches[0]


def _trade_planner_build_call():
    source = _source(
        SERVICE_PATH
    )
    tree = ast.parse(
        source
    )

    matches = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if (
            _render(
                source,
                node.func,
            )
            != "self.trade_planner_v2.build"
        ):
            continue

        keywords = {
            keyword.arg:
                keyword.value
            for keyword
            in node.keywords
            if keyword.arg
            is not None
        }

        matches.append(
            (
                node,
                keywords,
                source,
            )
        )

    assert len(matches) == 1

    return matches[0]


def _stage_rr_source(
    stage_name: str,
) -> str:
    source = _source(
        SERVICE_PATH
    )
    tree = ast.parse(
        source
    )

    matches = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if (
            _render(
                source,
                node.func,
            )
            != stage_name
        ):
            continue

        keywords = {
            keyword.arg:
                keyword.value
            for keyword
            in node.keywords
            if keyword.arg
            is not None
        }

        if (
            "reward_risk_ratio"
            not in keywords
        ):
            continue

        matches.append(
            _render(
                source,
                keywords[
                    "reward_risk_ratio"
                ],
            )
        )

    assert len(matches) == 1

    return matches[0]


def _planner_build_function():
    tree = _tree(
        PLANNER_PATH
    )

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
        and node.name == "build"
    ]

    assert len(matches) == 1

    return matches[0]


def test_service_analyze_has_reward_risk_ratio_parameter():
    fn = _service_analyze_function()

    arguments = (
        list(fn.args.posonlyargs)
        + list(fn.args.args)
        + list(fn.args.kwonlyargs)
    )

    names = [
        argument.arg
        for argument in arguments
    ]

    assert (
        "reward_risk_ratio"
        in names
    )


def test_risk_stage_keeps_analyze_reward_risk_ratio():
    assert (
        _stage_rr_source(
            "RiskStage"
        )
        == "reward_risk_ratio"
    )


def test_decision_stage_keeps_analyze_reward_risk_ratio():
    assert (
        _stage_rr_source(
            "DecisionStage"
        )
        == "reward_risk_ratio"
    )


def test_trade_planner_build_has_no_literal_reward_risk_2_0():
    _, keywords, _ = (
        _trade_planner_build_call()
    )

    value = keywords[
        "reward_risk_ratio"
    ]

    assert not (
        isinstance(
            value,
            ast.Constant,
        )
        and isinstance(
            value.value,
            (int, float),
        )
        and float(
            value.value
        ) == 2.0
    )


def test_trade_planner_build_uses_analyze_reward_risk_ratio():
    _, keywords, source = (
        _trade_planner_build_call()
    )

    value = keywords[
        "reward_risk_ratio"
    ]

    assert (
        _render(
            source,
            value,
        )
        == "reward_risk_ratio"
    )


def test_planner_request_and_minimum_policy_remain_distinct():
    source = _source(
        PLANNER_PATH
    )
    fn = _planner_build_function()

    arguments = (
        list(fn.args.posonlyargs)
        + list(fn.args.args)
        + list(fn.args.kwonlyargs)
    )

    argument_names = {
        argument.arg
        for argument in arguments
    }

    assert (
        "reward_risk_ratio"
        in argument_names
    )

    minimum_refs = []

    for node in ast.walk(fn):
        if not isinstance(
            node,
            ast.Attribute,
        ):
            continue

        if (
            _render(
                source,
                node,
            )
            == (
                "self."
                "minimum_reward_risk_ratio"
            )
        ):
            minimum_refs.append(
                node
            )

    assert minimum_refs


def test_market_auto_reward_risk_remains_deferred():
    source = _source(
        MARKET_PATH
    )
    tree = ast.parse(
        source
    )

    matches = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if (
            _render(
                source,
                node.func,
            )
            != "service.analyze"
        ):
            continue

        keywords = {
            keyword.arg:
                keyword.value
            for keyword
            in node.keywords
            if keyword.arg
            is not None
        }

        if (
            _render(
                source,
                keywords.get(
                    "account_balance"
                ),
            )
            if keywords.get(
                "account_balance"
            )
            is not None
            else None
        ) != "available_balance":
            continue

        matches.append(
            keywords
        )

    assert len(matches) == 1

    value = matches[0][
        "reward_risk_ratio"
    ]

    assert (
        _render(
            source,
            value,
        )
        == "2.0"
    )


def test_execution_confidence_remains_deferred():
    source = _source(
        APPROVAL_PATH
    )
    tree = ast.parse(
        source
    )

    matches = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if (
            _render(
                source,
                node.func,
            )
            != (
                "execution_engine."
                "validate_execution"
            )
        ):
            continue

        keywords = {
            keyword.arg:
                keyword.value
            for keyword
            in node.keywords
            if keyword.arg
            is not None
        }

        if "confidence" in keywords:
            matches.append(
                keywords["confidence"]
            )

    assert len(matches) == 1

    assert (
        _render(
            source,
            matches[0],
        )
        == "98"
    )


def test_live_position_current_price_remains_deferred():
    source = _source(
        PIPELINE_PATH
    )
    tree = ast.parse(
        source
    )

    matches = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        func = _render(
            source,
            node.func,
        )

        if (
            "live_position_monitor_v2"
            not in func
            or not func.endswith(
                ".process_price"
            )
        ):
            continue

        keywords = {
            keyword.arg:
                keyword.value
            for keyword
            in node.keywords
            if keyword.arg
            is not None
        }

        if "current_price" in keywords:
            matches.append(
                keywords[
                    "current_price"
                ]
            )

    assert len(matches) == 1

    assert (
        _render(
            source,
            matches[0],
        )
        == "23650"
    )
