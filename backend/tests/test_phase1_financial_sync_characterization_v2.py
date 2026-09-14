from __future__ import annotations

import ast
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    path = BACKEND_ROOT / relative_path
    assert path.is_file(), f"Expected repository file is missing: {path}"
    return path.read_text(encoding="utf-8")


def _defined_names(source: str) -> set[str]:
    tree = ast.parse(source)
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_financial_state_participants_are_present() -> None:
    expected_files = (
        "account/account_state_manager_v2.py",
        "portfolio/portfolio_manager_v2.py",
        "journal/trade_journal_v2.py",
        "analytics/trade_history_manager_v2.py",
        "services/signal_history_store.py",
        "services/trade_history_store.py",
        "execution/position_manager_v2.py",
        "execution/oco_manager_v2.py",
        "execution/protective_order_registry_v2.py",
    )

    for relative_path in expected_files:
        source = _source(relative_path)
        assert source.strip()
        assert _defined_names(source), relative_path


def test_lifecycle_source_references_financial_synchronization_domains() -> None:
    lifecycle_source = _source(
        "services/trade_lifecycle_service_v2.py"
    ).lower()

    required_domains = (
        "position",
        "portfolio",
        "account",
        "journal",
        "history",
        "protection",
        "oco",
    )

    missing = [
        domain
        for domain in required_domains
        if domain not in lifecycle_source
    ]
    assert not missing, f"Lifecycle source lacks domains: {missing}"


def test_financial_sync_sources_include_open_and_close_operations() -> None:
    lifecycle_source = _source(
        "services/trade_lifecycle_service_v2.py"
    ).lower()
    portfolio_source = _source("portfolio/portfolio_manager_v2.py").lower()
    journal_source = _source("journal/trade_journal_v2.py").lower()
    history_source = _source(
        "analytics/trade_history_manager_v2.py"
    ).lower()

    combined = "\n".join(
        (lifecycle_source, portfolio_source, journal_source, history_source)
    )

    assert "open" in combined
    assert "close" in combined
    assert "pnl" in combined or "profit" in combined
    assert "sync" in combined or "update" in combined
