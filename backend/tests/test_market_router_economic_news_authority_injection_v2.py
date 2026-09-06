from __future__ import annotations

import ast
from pathlib import Path


ROUTER_PATH = Path(
    "backend/api/routers/market.py"
)


def _load_router():
    source = ROUTER_PATH.read_text(
        encoding="utf-8"
    )

    return source, ast.parse(source)


def _live_service_calls():
    _, tree = _load_router()

    calls = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if (
            isinstance(func, ast.Name)
            and func.id == "LiveMarketAnalysisService"
        ):
            calls.append(node)

    return sorted(
        calls,
        key=lambda node: node.lineno,
    )


def _keyword_value(
    call: ast.Call,
    keyword_name: str,
):
    for keyword in call.keywords:
        if keyword.arg == keyword_name:
            return keyword.value

    return None


def _is_exact_request_app_state_authority(
    node,
) -> bool:
    if not isinstance(node, ast.Attribute):
        return False

    if node.attr != "economic_news_authority_v2":
        return False

    state = node.value

    if not isinstance(state, ast.Attribute):
        return False

    if state.attr != "state":
        return False

    app = state.value

    if not isinstance(app, ast.Attribute):
        return False

    if app.attr != "app":
        return False

    request = app.value

    return (
        isinstance(request, ast.Name)
        and request.id == "request"
    )


def test_market_router_has_exactly_two_live_service_construction_sites():
    calls = _live_service_calls()

    assert len(calls) == 2


def test_both_live_service_construction_sites_inject_economic_news_authority():
    calls = _live_service_calls()

    assert len(calls) == 2

    for call in calls:
        value = _keyword_value(
            call,
            "economic_news_authority_v2",
        )

        assert value is not None, (
            "LiveMarketAnalysisService construction "
            f"at line {call.lineno} must inject "
            "economic_news_authority_v2"
        )


def test_both_router_injections_use_exact_app_state_authority():
    calls = _live_service_calls()

    assert len(calls) == 2

    for call in calls:
        value = _keyword_value(
            call,
            "economic_news_authority_v2",
        )

        assert value is not None, (
            "missing economic_news_authority_v2 "
            f"at line {call.lineno}"
        )

        assert (
            _is_exact_request_app_state_authority(
                value
            )
        ), (
            "economic_news_authority_v2 must be "
            "request.app.state."
            "economic_news_authority_v2 "
            f"at line {call.lineno}"
        )


def test_market_router_does_not_construct_economic_news_runtime_components():
    source, tree = _load_router()

    forbidden_calls = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if not isinstance(func, ast.Name):
            continue

        if func.id in {
            "EconomicNewsAuthorityV2",
            "EconomicNewsRuntimeProviderV2",
            "CertifiedEconomicNewsDataLifecycleV2",
        }:
            forbidden_calls.append(
                (
                    func.id,
                    node.lineno,
                )
            )

    assert forbidden_calls == []

    assert (
        source.count(
            "request.app.state."
            "economic_news_authority_v2"
        )
        == 2
    )
