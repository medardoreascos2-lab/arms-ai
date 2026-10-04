"""R89A MEDAR financial routing tests."""

import pytest

from backend.medar.financial_router import FinancialProduct, route_financial_task


def test_financial_products_route_to_explicit_current_modules():
    assert route_financial_task(FinancialProduct.STOCK, "AAPL").target_module == "backend.financial.scorecard"
    assert route_financial_task(FinancialProduct.ETF, "QQQ").target_module == "backend.financial.etf"
    assert route_financial_task(FinancialProduct.CRYPTO, "BTC").target_module == "backend.financial.crypto_scanner"
    assert route_financial_task(FinancialProduct.PORTFOLIO).target_module == "backend.financial.portfolio_guardian"
    assert route_financial_task(FinancialProduct.ARBITRAGE).target_module == "backend.financial.arbitrage_ranking"


def test_futures_route_uses_phase6_canonical_registry_without_execution_authority():
    route = route_financial_task(FinancialProduct.FUTURES, "NQ")
    assert route.target_module == "backend.phase6"
    assert route.instrument.root_symbol == "NQ"
    assert route.execution_authority is False


def test_futures_without_instrument_fail_closed():
    with pytest.raises(ValueError, match="instrument"):
        route_financial_task(FinancialProduct.FUTURES)
