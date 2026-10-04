"""F101D: company comparisons require aligned evidence."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.financial.comparison import ComparisonStatus, compare_companies
from backend.financial.fundamentals import CompanyFundamentals, FundamentalObservation

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def company(asset, period="2026-Q2", currency="USD", unit="USD", include=True):
    observations = {"revenue": FundamentalObservation(Decimal("100"), unit, period, f"synthetic:{asset}", NOW)} if include else {}
    return CompanyFundamentals(asset, currency, period, observations)


def test_comparable_result_retains_both_sources():
    result = compare_companies(company("A"), company("B"), "revenue")
    assert result.status is ComparisonStatus.COMPARABLE
    assert result.difference == Decimal("0")
    assert result.left_source == "synthetic:A" and result.right_source == "synthetic:B"


def test_missing_metric_is_unknown_and_mismatched_basis_rejected():
    result = compare_companies(company("A"), company("B", include=False), "revenue")
    assert result.status is ComparisonStatus.INCOMPLETE_DATA
    assert result.difference is None
    with pytest.raises(ValueError, match="period"):
        compare_companies(company("A"), company("B", period="2026-Q1"), "revenue")
    with pytest.raises(ValueError, match="currency"):
        compare_companies(company("A"), company("B", currency="EUR"), "revenue")
    with pytest.raises(ValueError, match="unit"):
        compare_companies(company("A"), company("B", unit="shares"), "revenue")
