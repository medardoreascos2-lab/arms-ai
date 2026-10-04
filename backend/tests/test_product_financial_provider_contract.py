"""P104-PRE2 Product financial provider is structurally read-only."""

import inspect

from backend.product.financial_provider import ProductFinancialReadProvider


EXPECTED_READ_METHODS = {
    "get_trading_summary",
    "get_nq_summary",
    "get_mnq_summary",
    "get_portfolio_summary",
    "get_portfolio_risk",
    "get_trading_coach_summary",
    "get_shadow_medar_summary",
    "get_financial_alerts",
    "get_daily_financial_snapshot",
}


def test_provider_contract_exposes_only_approved_read_methods():
    public = {
        name for name, value in inspect.getmembers(ProductFinancialReadProvider)
        if not name.startswith("_") and callable(value)
    }
    assert public == EXPECTED_READ_METHODS


def test_provider_contract_contains_no_mutation_vocabulary():
    forbidden = {
        "place", "submit", "cancel", "modify", "update", "delete", "rebalance",
        "withdraw", "deposit", "execute", "enable", "connect", "link",
    }
    for name in EXPECTED_READ_METHODS:
        assert not any(word in name.lower() for word in forbidden)
