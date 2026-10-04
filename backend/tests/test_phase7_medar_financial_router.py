"""R89A MEDAR financial routing tests."""

import pytest

from backend.medar.financial_router import FinancialProduct, route_financial_task


def test_financial_products_route_to_explicit_current_or_future_modules():
    assert route_financial_task(FinancialProduct.STOCK, "AAPL").target_module == "future.stocks"
    assert route_financial_task(FinancialProduct.ETF, "QQQ").target_module == "future.etfs"
    assert route_financial_task(FinancialProduct.CRYPTO, "BTC").target_module == "future.crypto"
    assert route_financial_task(FinancialProduct.PORTFOLIO).target_module == "future.portfolio"
    assert route_financial_task(FinancialProduct.ARBITRAGE).target_module == "future.crypto_arbitrage"


def test_futures_route_uses_phase6_canonical_registry_without_execution_authority():
    route = route_financial_task(FinancialProduct.FUTURES, "NQ")
    assert route.target_module == "backend.phase6"
    assert route.instrument.root_symbol == "NQ"
    assert route.execution_authority is False


def test_futures_without_instrument_fail_closed():
    with pytest.raises(ValueError, match="instrument"):
        route_financial_task(FinancialProduct.FUTURES)
