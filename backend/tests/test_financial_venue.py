"""F100B: provider-neutral venue registry."""

import pytest

from backend.financial.asset import AssetType
from backend.financial.venue import FinancialVenue, VenueDataStatus, VENUES, get_venue


def test_required_venue_identifiers_have_explicit_unknown_runtime_state():
    assert {"CME", "NASDAQ", "NYSE", "ARCA", "COINBASE", "KRAKEN", "BINANCE"} <= VENUES.keys()
    assert all(venue.data_status is VenueDataStatus.UNKNOWN for venue in VENUES.values())
    assert all(venue.market_hours is None and venue.fee_model_reference is None for venue in VENUES.values())
    assert AssetType.FUTURE in get_venue("cme").asset_classes
    assert AssetType.CRYPTO_SPOT in get_venue("kraken").asset_classes


def test_registry_cannot_be_mutated_and_unknown_venue_does_not_fallback():
    with pytest.raises(TypeError):
        VENUES["UNKNOWN"] = get_venue("CME")
    with pytest.raises(KeyError, match="unknown venue"):
        get_venue("not-registered")


def test_invalid_venue_metadata_rejected():
    with pytest.raises(ValueError, match="asset_classes"):
        FinancialVenue("X", "X", (), "UTC")
    with pytest.raises(TypeError, match="data_status"):
        FinancialVenue("X", "X", (AssetType.STOCK,), "UTC", data_status="AVAILABLE")
