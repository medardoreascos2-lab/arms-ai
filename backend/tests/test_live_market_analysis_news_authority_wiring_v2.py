from __future__ import annotations

import ast
from pathlib import Path


LIVE_PATH = Path(
    "backend/services/live_market_analysis_service.py"
)


def _tree() -> ast.Module:
    return ast.parse(
        LIVE_PATH.read_text(
            encoding="utf-8"
        )
    )


def _live_class() -> ast.ClassDef:
    tree = _tree()

    for node in tree.body:
        if (
            isinstance(node, ast.ClassDef)
            and node.name == "LiveMarketAnalysisService"
        ):
            return node

    raise AssertionError(
        "LiveMarketAnalysisService not found"
    )


def _init() -> ast.FunctionDef:
    live_class = _live_class()

    for node in live_class.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "__init__"
        ):
            return node

    raise AssertionError(
        "LiveMarketAnalysisService.__init__ not found"
    )


def _analyze() -> ast.FunctionDef | ast.AsyncFunctionDef:
    live_class = _live_class()

    for node in live_class.body:
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == "analyze"
        ):
            return node

    raise AssertionError(
        "LiveMarketAnalysisService.analyze not found"
    )


def _news_blocked_keywords() -> list[ast.keyword]:
    analyze = _analyze()

    keywords: list[ast.keyword] = []

    for node in ast.walk(analyze):
        if not isinstance(node, ast.Call):
            continue

        for keyword in node.keywords:
            if keyword.arg == "news_blocked":
                keywords.append(keyword)

    return keywords


def test_live_service_declares_news_authority_dependency():
    init = _init()

    argument_names = {
        arg.arg
        for arg in (
            list(init.args.args)
            + list(init.args.kwonlyargs)
        )
    }

    assert (
        "economic_news_authority_v2"
        in argument_names
    )


def test_live_service_stores_news_authority_dependency():
    init = _init()

    assignments = []

    for node in ast.walk(init):
        if not isinstance(
            node,
            (
                ast.Assign,
                ast.AnnAssign,
            ),
        ):
            continue

        targets = []

        if isinstance(node, ast.Assign):
            targets = node.targets
        else:
            targets = [node.target]

        for target in targets:
            try:
                target_text = ast.unparse(target)
            except Exception:
                continue

            if (
                target_text
                == "self.economic_news_authority_v2"
            ):
                assignments.append(node)

    assert len(assignments) == 1


def test_analyze_evaluates_news_authority_exactly_once():
    analyze = _analyze()

    calls = []

    for node in ast.walk(analyze):
        if not isinstance(node, ast.Call):
            continue

        try:
            call_name = ast.unparse(node.func)
        except Exception:
            continue

        if (
            call_name
            == (
                "self.economic_news_authority_v2."
                "is_news_blocked"
            )
        ):
            calls.append(node)

    assert len(calls) == 1

    call = calls[0]

    keyword_map = {
        keyword.arg: ast.unparse(keyword.value)
        for keyword in call.keywords
        if keyword.arg is not None
    }

    assert keyword_map["symbol"] == "symbol"

    assert keyword_map["timestamp"] in {
        'result["analyzed_at"]',
        "result['analyzed_at']",
        "candles[-1].timestamp",
    }


def test_both_downstream_consumers_use_same_runtime_news_value():
    keywords = _news_blocked_keywords()

    assert len(keywords) == 2

    values = [
        ast.unparse(keyword.value)
        for keyword in keywords
    ]

    assert values[0] == values[1]

    assert values[0] not in {
        "False",
        "True",
        "None",
    }


def test_no_static_news_blocked_bypass_remains():
    keywords = _news_blocked_keywords()

    assert len(keywords) == 2

    for keyword in keywords:
        assert not isinstance(
            keyword.value,
            ast.Constant,
        )
