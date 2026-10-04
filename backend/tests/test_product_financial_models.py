"""P104-PRE3 Product financial projection contract tests."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.product.financial_models import (
    FinancialProjectionStatus,
    FinancialSourceStatus,
    PortfolioSummaryProjection,
    ProductFinancialProvenance,
    TradingSummaryProjection,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def provenance(**overrides):
    body = {
        "source_id": "synthetic-source-1",
        "source_label": "Synthetic local fixture",
        "classification": "SYNTHETIC",
        "observed_at": NOW,
        "freshness_seconds": 0,
        "source_status": FinancialSourceStatus.SYNTHETIC,
    }
    body.update(overrides)
    return ProductFinancialProvenance(**body)


def test_trading_projection_requires_provenance_and_has_no_execution_authority():
    projection = TradingSummaryProjection(
        status=FinancialProjectionStatus.READY,
        provenance=provenance(),
        instrument="NQ",
        account_ref="synthetic-account-nq",
        market_state="RANGE",
        risk_state="WATCH",
        session_state="OPEN",
        data_freshness="CURRENT",
        source_status=FinancialSourceStatus.SYNTHETIC,
    )
    assert projection.execution_authorized is False
    assert projection.portfolio_mutation_authorized is False
    assert projection.investment_advice is False
    with pytest.raises(ValidationError):
        TradingSummaryProjection.model_validate({
            **projection.model_dump(), "execution_authorized": True,
        })


def test_unknown_portfolio_values_remain_none_instead_of_fabricated_zero():
    projection = PortfolioSummaryProjection(
        status=FinancialProjectionStatus.UNKNOWN,
        provenance=provenance(
            classification="UNKNOWN", observed_at=None,
            freshness_seconds=None, source_status=FinancialSourceStatus.UNKNOWN,
        ),
        currency="UNKNOWN",
        total_value=None,
        cash=None,
        drawdown=None,
        source_status=FinancialSourceStatus.UNKNOWN,
    )
    assert projection.total_value is None
    assert projection.cash is None
    assert projection.drawdown is None
    assert projection.allocation == ()


def test_unknown_provenance_cannot_claim_freshness_and_values_are_bounded():
    with pytest.raises(ValidationError):
        provenance(source_status=FinancialSourceStatus.UNKNOWN)
    with pytest.raises(ValidationError):
        PortfolioSummaryProjection(
            status="READY",
            provenance=provenance(),
            total_value=Decimal("-1"),
            source_status="SYNTHETIC",
        )
