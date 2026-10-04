"""F101A: company fundamentals preserve missingness and provenance."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.financial.fundamentals import CompanyFundamentals, FundamentalObservation

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def observation(period="2026-Q2"):
    return FundamentalObservation(Decimal("100"), "USD", period, "synthetic:filing", NOW)


def test_missing_fundamentals_remain_unknown_and_evidence_is_immutable():
    supplied = {"revenue": observation()}
    company = CompanyFundamentals("NASDAQ:TEST", "USD", "2026-Q2", supplied)
    supplied.clear()
    assert company.get("revenue").value == Decimal("100")
    assert company.get("earnings") is None
    with pytest.raises(TypeError):
        company.observations["earnings"] = observation()


def test_mismatched_period_and_unevidenced_guidance_rejected():
    with pytest.raises(ValueError, match="period mismatch"):
        CompanyFundamentals("NASDAQ:TEST", "USD", "2026-Q2", {"revenue": observation("2026-Q1")})
    with pytest.raises(ValueError, match="guidance requires source"):
        CompanyFundamentals("NASDAQ:TEST", "USD", "2026-Q2", guidance="up")
    with pytest.raises(ValueError, match="unsupported"):
        CompanyFundamentals("NASDAQ:TEST", "USD", "2026-Q2", {"fabricated": observation()})
