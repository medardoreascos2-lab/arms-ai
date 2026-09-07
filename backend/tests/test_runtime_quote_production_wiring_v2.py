from __future__ import annotations

import ast
from pathlib import Path


APP_PATH = Path("backend/api/app.py")
SETTINGS_PATH = Path("backend/config/api_settings.py")
MARKET_ROUTER_PATH = Path(
    "backend/api/routers/market.py"
)
MARKET_SCHEMA_PATH = Path(
    "backend/api/schemas/market.py"
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tree(path: Path) -> ast.AST:
    return ast.parse(_source(path))


def _live_service_calls() -> list[ast.Call]:
    tree = _tree(MARKET_ROUTER_PATH)

    calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        try:
            function_name = ast.unparse(node.func)
        except Exception:
            continue

        if function_name == "LiveMarketAnalysisService":
            calls.append(node)

    return calls


def test_api_settings_owns_runtime_quote_freshness_policy():
    source = _source(SETTINGS_PATH)

    assert "maximum_quote_age_seconds" in source
    assert "ARMS_MAXIMUM_QUOTE_AGE_SECONDS" in source


def test_app_constructs_runtime_quote_authority():
    source = _source(APP_PATH)

    assert "RuntimeQuoteAuthorityV2" in source
    assert "runtime_quote_authority_v2" in source


def test_app_constructs_spread_authority():
    source = _source(APP_PATH)

    assert "SpreadAuthorityV2" in source
    assert "spread_authority_v2" in source


def test_app_constructs_runtime_spread_authority():
    source = _source(APP_PATH)

    assert "RuntimeSpreadAuthorityV2" in source
    assert "runtime_spread_authority_v2" in source
    assert "maximum_quote_age_seconds" in source


def test_all_production_live_services_receive_runtime_spread_authority():
    calls = _live_service_calls()

    assert len(calls) == 2

    for call in calls:
        keywords = {
            keyword.arg
            for keyword in call.keywords
            if keyword.arg is not None
        }

        assert (
            "runtime_spread_authority_v2"
            in keywords
        )


def test_market_api_exposes_explicit_l1_bid_ask_ingestion():
    schema_source = _source(MARKET_SCHEMA_PATH)
    router_source = _source(MARKET_ROUTER_PATH)

    assert "bid" in schema_source
    assert "ask" in schema_source

    assert "publish_quote" in router_source
    assert "runtime_quote_authority_v2" in router_source


def test_quote_ingestion_does_not_synthesize_bid_ask_from_ohlc():
    router_source = _source(MARKET_ROUTER_PATH)

    forbidden = (
        "bid=payload.close",
        "ask=payload.close",
        "bid=payload.open",
        "ask=payload.open",
        "bid=payload.high",
        "ask=payload.high",
        "bid=payload.low",
        "ask=payload.low",
    )

    for expression in forbidden:
        assert expression not in router_source


def test_quote_ingestion_does_not_use_tick_size_as_quote():
    router_source = _source(MARKET_ROUTER_PATH)

    forbidden = (
        "bid=tick_size",
        "ask=tick_size",
        "spread=tick_size",
    )

    for expression in forbidden:
        assert expression not in router_source
