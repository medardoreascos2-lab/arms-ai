"""R89B regression coverage for exact NQ/MNQ routing."""

from decimal import Decimal

import pytest

from backend.medar.financial_router import FinancialProduct, route_financial_task
from backend.phase6.instrument_registry import InstrumentRegistryError


def test_nq_and_mnq_remain_distinct_canonical_instruments():
    nq = route_financial_task(FinancialProduct.FUTURES, "NQ")
    mnq = route_financial_task(FinancialProduct.FUTURES, "MNQ")

    assert nq.symbol == "NQ"
    assert mnq.symbol == "MNQ"
    assert nq.instrument is not mnq.instrument
    assert nq.instrument.point_value == Decimal("20.00")
    assert mnq.instrument.point_value == Decimal("2.00")
    assert nq.instrument.tick_value == Decimal("5.0000")
    assert mnq.instrument.tick_value == Decimal("0.5000")


@pytest.mark.parametrize("symbol", ("ES", "MES", "", "NQ/MNQ"))
def test_unknown_or_ambiguous_futures_symbols_are_never_substituted(symbol):
    expected = ValueError if symbol == "" else InstrumentRegistryError
    with pytest.raises(expected):
        route_financial_task(FinancialProduct.FUTURES, symbol)
