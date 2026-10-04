"""F104D: basis is measured without leverage or execution."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.financial.basis import BasisQuote, CryptoMarketKind, analyze_basis

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def test_perpetual_basis_preserves_funding_as_separate_evidence():
    spot = BasisQuote("BTC-SPOT", "BTC", "USD", CryptoMarketKind.SPOT,
                      Decimal("100"), NOW, "synthetic:spot")
    perp = BasisQuote("BTC-PERP", "BTC", "USD", CryptoMarketKind.PERPETUAL,
                      Decimal("102"), NOW, "synthetic:perp",
                      funding_rate_per_interval=Decimal("0.0001"))
    result = analyze_basis(spot, perp, NOW, timedelta(seconds=30))
    assert result.basis_quote == Decimal("2")
    assert result.basis_fraction == Decimal("0.02")
    assert result.funding_rate_per_interval == Decimal("0.0001")
    assert result.analysis_only and not hasattr(result, "leverage")


def test_stale_basis_quote_rejected():
    spot = BasisQuote("BTC-SPOT", "BTC", "USD", CryptoMarketKind.SPOT,
                      Decimal("100"), NOW - timedelta(minutes=1), "synthetic:spot")
    perp = BasisQuote("BTC-PERP", "BTC", "USD", CryptoMarketKind.PERPETUAL,
                      Decimal("102"), NOW, "synthetic:perp")
    with pytest.raises(ValueError, match="fresh"):
        analyze_basis(spot, perp, NOW, timedelta(seconds=30))
