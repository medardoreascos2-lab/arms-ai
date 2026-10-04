"""F100A: canonical financial asset identity and authority boundaries."""

from decimal import Decimal

import pytest

from backend.financial.asset import AssetType, FinancialAsset


def test_asset_types_are_explicit_and_metadata_is_immutable():
    assert {kind.value for kind in AssetType} == {
        "FUTURE", "STOCK", "ETF", "CRYPTO_SPOT", "CRYPTO_PERPETUAL",
        "FOREX", "INDEX", "CASH", "STABLECOIN",
    }
    source = {"sector": "technology"}
    asset = FinancialAsset("NASDAQ:AAPL", "AAPL", "NASDAQ", "USD", AssetType.STOCK, metadata=source)
    source["sector"] = "changed"
    assert asset.metadata["sector"] == "technology"
    with pytest.raises(TypeError):
        asset.metadata["sector"] = "changed"


def test_nq_and_mnq_remain_distinct_explicit_contracts():
    nq = FinancialAsset("CME:NQ:2026-12", "NQ", "CME", "USD", AssetType.FUTURE,
                        Decimal("20"), Decimal("0.25"), Decimal("20"))
    mnq = FinancialAsset("CME:MNQ:2026-12", "MNQ", "CME", "USD", AssetType.FUTURE,
                         Decimal("2"), Decimal("0.25"), Decimal("2"))
    assert nq.asset_id != mnq.asset_id
    assert nq.point_value != mnq.point_value


@pytest.mark.parametrize("field,value", [
    ("tick_size", Decimal("NaN")), ("point_value", Decimal("0")),
    ("contract_multiplier", Decimal("-1")),
])
def test_invalid_contract_specification_rejected(field, value):
    fields = dict(asset_id="CME:NQ:2026-12", symbol="NQ", venue="CME",
                  currency="USD", asset_type=AssetType.FUTURE,
                  contract_multiplier=Decimal("20"), tick_size=Decimal("0.25"),
                  point_value=Decimal("20"))
    fields[field] = value
    with pytest.raises(ValueError):
        FinancialAsset(**fields)


def test_derivative_missing_specs_fail_closed_but_unknown_stock_specs_stay_unknown():
    with pytest.raises(ValueError, match="contract specifications"):
        FinancialAsset("CME:NQ:2026-12", "NQ", "CME", "USD", AssetType.FUTURE)
    stock = FinancialAsset("NASDAQ:TEST", "TEST", "NASDAQ", "USD", AssetType.STOCK)
    assert stock.tick_size is None and stock.point_value is None
    assert not hasattr(stock, "execution_authority")
