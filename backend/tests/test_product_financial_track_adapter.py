"""P104-PRE10 future Financial Track adapter remains an unbound fail-closed seam."""

import ast
import inspect

import pytest

from backend.product.financial_models import FinancialReadStatus
from backend.product.financial_provider import ProductFinancialReadProvider
from backend.product.financial_track_adapter import (
    FinancialTrackIntegrationPending,
    PendingFinancialTrackAdapter,
)
from backend.tests.test_product_financial_access import fixture


def test_pending_adapter_matches_read_contract_and_returns_no_data():
    expected = {
        name for name, value in inspect.getmembers(ProductFinancialReadProvider)
        if not name.startswith("_") and callable(value)
    }
    adapter = PendingFinancialTrackAdapter()
    assert expected.issubset({
        name for name, value in inspect.getmembers(adapter)
        if not name.startswith("_") and callable(value)
    })
    assert adapter.readiness() == FinancialReadStatus.INTEGRATION_PENDING
    scope = fixture()[2]
    for method in expected:
        with pytest.raises(FinancialTrackIntegrationPending):
            getattr(adapter, method)(scope)


def test_adapter_imports_no_financial_track_implementation():
    path = "backend/product/financial_track_adapter.py"
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    imported = {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(name.startswith((
        "backend.financial", "backend.portfolio", "backend.execution",
        "backend.accounts", "backend.medar.financial",
    )) for name in imported)
