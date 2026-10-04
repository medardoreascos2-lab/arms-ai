"""P104-PRE9 Product financial reads have no mutation authority or dependency path."""

import ast
import inspect
from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError

from backend.api.product_financial_local_test import create_local_test_product_financial_app
from backend.product.financial_access import CustomerFinancialAccessScope
from backend.product.financial_models import ProductFinancialDegradedResponse
from backend.product.financial_provider import ProductFinancialReadProvider
from backend.product.synthetic_financial_provider import LocalSyntheticFinancialProvider
from backend.tests.test_product_financial_access import fixture as access_fixture


FORBIDDEN_ACTIONS = {
    "place_order", "submit_order", "cancel_order", "modify_position",
    "modify_portfolio", "rebalance", "withdraw", "deposit",
    "enable_paper", "enable_live", "grant_broker_authority",
}
FORBIDDEN_IMPORT_ROOTS = {
    "backend.execution",
    "backend.connectors",
    "backend.accounts",
    "backend.portfolio",
}


def public_methods(contract):
    return {
        name for name, value in inspect.getmembers(contract)
        if not name.startswith("_") and callable(value)
    }


def test_read_contract_and_synthetic_provider_have_no_mutation_methods():
    assert FORBIDDEN_ACTIONS.isdisjoint(public_methods(ProductFinancialReadProvider))
    assert FORBIDDEN_ACTIONS.isdisjoint(public_methods(LocalSyntheticFinancialProvider))


def test_default_product_financial_http_surface_is_get_only():
    app = create_local_test_product_financial_app()
    paths = app.openapi()["paths"]
    assert paths
    for path, operations in paths.items():
        assert path.startswith("/product/financial/")
        assert set(operations) == {"get"}


def test_scope_and_degraded_contract_cannot_enable_authority():
    _, _, scope = access_fixture()
    with pytest.raises(FrozenInstanceError):
        scope.live_authorized = True
    for field in (
        "broker_authorized", "portfolio_mutation_authorized",
        "paper_authorized", "live_authorized",
    ):
        with pytest.raises(ValidationError):
            ProductFinancialDegradedResponse.model_validate({
                "status": "FINANCIAL_DATA_UNAVAILABLE", field: True,
            })


@pytest.mark.parametrize("path", [
    "backend/product/financial_access.py",
    "backend/product/financial_authorization.py",
    "backend/product/financial_provider.py",
    "backend/product/financial_models.py",
    "backend/product/synthetic_financial_provider.py",
    "backend/api/product_financial_api.py",
    "backend/api/product_financial_local_test.py",
])
def test_boundary_imports_no_execution_broker_account_or_portfolio_implementation(path):
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not {
        name for name in imported
        if any(name == root or name.startswith(root + ".") for root in FORBIDDEN_IMPORT_ROOTS)
    }
