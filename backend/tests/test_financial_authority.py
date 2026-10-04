"""F113A: new financial modules contain no execution-capability imports or calls."""

import ast
from pathlib import Path

import pytest

from backend.financial.authority import FINANCIAL_AUTHORITY, FinancialAuthority

FINANCIAL_ROOT = Path(__file__).resolve().parents[1] / "financial"
API_FILE = Path(__file__).resolve().parents[1] / "api" / "financial_intelligence_api_v1.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "backend.execution", "backend.connectors", "backend.accounts",
    "backend.services.trade_lifecycle_service", "backend.storage.journal_database",
)
FORBIDDEN_CALLS = {
    "place_order", "submit_order", "execute_order", "transfer_funds",
    "withdraw_crypto", "enable_live", "enable_paper", "record_open_trade",
    "close_trade",
}


def test_authority_ceiling_rejects_every_execution_or_mutation_flag():
    assert not any(vars(FINANCIAL_AUTHORITY).values())
    for field in vars(FINANCIAL_AUTHORITY):
        with pytest.raises(ValueError, match="analysis only"):
            FinancialAuthority(**{field: True})


def test_financial_modules_do_not_import_or_call_execution_capabilities():
    for path in (*FINANCIAL_ROOT.glob("*.py"), API_FILE):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(FORBIDDEN_IMPORT_PREFIXES), (path, node.module)
            if isinstance(node, ast.Import):
                assert all(not item.name.startswith(FORBIDDEN_IMPORT_PREFIXES) for item in node.names), path
            if isinstance(node, ast.Call):
                called = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else None
                assert called not in FORBIDDEN_CALLS, (path, called)
