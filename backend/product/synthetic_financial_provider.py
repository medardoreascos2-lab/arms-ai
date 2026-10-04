"""Deterministic local-only Product financial observations.

These fixtures are intentionally synthetic. They perform no network, broker, exchange,
account, portfolio, PAPER, or LIVE operation.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal

from backend.product.financial_access import (
    CustomerFinancialAccessScope,
    ProductFinancialSurface,
)
from backend.product.financial_models import (
    DailyFinancialSnapshot,
    FinancialAlert,
    FinancialAlertCollection,
    FinancialProjectionStatus,
    FinancialSourceStatus,
    PortfolioAllocation,
    PortfolioRiskProjection,
    PortfolioSummaryProjection,
    ProductFinancialProvenance,
    ShadowMedarProjection,
    TradingCoachProjection,
    TradingSummaryProjection,
)


LOCAL_TEST_ONLY = "LOCAL_TEST_ONLY"
SYNTHETIC_WARNING = "SYNTHETIC LOCAL_TEST_ONLY NOT_REAL_ACCOUNT_DATA"


class LocalSyntheticFinancialProvider:
    """Read-only deterministic provider for one server-issued synthetic scope."""

    def __init__(self, scope: CustomerFinancialAccessScope, observed_at: datetime) -> None:
        if not isinstance(scope, CustomerFinancialAccessScope) or scope.source != LOCAL_TEST_ONLY:
            raise ValueError("LOCAL_TEST_ONLY financial scope required")
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        self._scope = scope
        self._observed_at = observed_at
        self.calls: Counter[str] = Counter()

    def _require(self, scope: CustomerFinancialAccessScope, surface: ProductFinancialSurface) -> None:
        if scope is not self._scope or surface not in scope.allowed_surfaces:
            raise PermissionError("trusted financial scope and allowed surface required")

    def _provenance(self, suffix: str) -> ProductFinancialProvenance:
        return ProductFinancialProvenance(
            source_id=f"synthetic-product-financial-{suffix}",
            source_label="Synthetic Product financial fixture",
            classification="SYNTHETIC",
            observed_at=self._observed_at,
            freshness_seconds=0,
            source_status=FinancialSourceStatus.SYNTHETIC,
        )

    def _trading(self, scope: CustomerFinancialAccessScope, instrument: str) -> TradingSummaryProjection:
        self._require(scope, ProductFinancialSurface.TRADING)
        account_ref = (
            "synthetic-account-nq" if instrument == "NQ" else "synthetic-account-mnq"
        )
        if account_ref not in scope.account_refs:
            raise PermissionError("instrument account is outside trusted scope")
        return TradingSummaryProjection(
            status=FinancialProjectionStatus.READY,
            provenance=self._provenance(instrument.lower()),
            warnings=(SYNTHETIC_WARNING,),
            instrument=instrument,
            account_ref=account_ref,
            market_state="RANGE",
            risk_state="WATCH",
            session_state="OPEN",
            coach_summary="Synthetic review: wait for verified confirmation.",
            alerts=(self._alert(),),
            data_freshness="SYNTHETIC_CURRENT",
            source_status=FinancialSourceStatus.SYNTHETIC,
        )

    @staticmethod
    def _alert() -> FinancialAlert:
        return FinancialAlert(
            alert_id="synthetic-alert-1",
            title="Synthetic risk review",
            detail="Local test fixture only; no real account exposure exists.",
            severity="WATCH",
        )

    def get_trading_summary(self, scope: CustomerFinancialAccessScope) -> TradingSummaryProjection:
        self.calls["get_trading_summary"] += 1
        return self._trading(scope, "NQ")

    def get_nq_summary(self, scope: CustomerFinancialAccessScope) -> TradingSummaryProjection:
        self.calls["get_nq_summary"] += 1
        return self._trading(scope, "NQ")

    def get_mnq_summary(self, scope: CustomerFinancialAccessScope) -> TradingSummaryProjection:
        self.calls["get_mnq_summary"] += 1
        return self._trading(scope, "MNQ")

    def get_portfolio_summary(self, scope: CustomerFinancialAccessScope) -> PortfolioSummaryProjection:
        self.calls["get_portfolio_summary"] += 1
        self._require(scope, ProductFinancialSurface.PORTFOLIO)
        if "synthetic-portfolio-1" not in scope.portfolio_refs:
            raise PermissionError("portfolio is outside trusted scope")
        return PortfolioSummaryProjection(
            status=FinancialProjectionStatus.READY,
            provenance=self._provenance("portfolio"),
            warnings=(SYNTHETIC_WARNING,),
            portfolio_ref="synthetic-portfolio-1",
            currency="USD",
            total_value=Decimal("17000.00"),
            cash=Decimal("17000.00"),
            allocation=(PortfolioAllocation(label="Synthetic cash", percentage=Decimal("100")),),
            concentration="SYNTHETIC_CASH_ONLY",
            risk="NO_REAL_EXPOSURE",
            drawdown=Decimal("0"),
            alerts=(self._alert(),),
            source_status=FinancialSourceStatus.SYNTHETIC,
        )

    def get_portfolio_risk(self, scope: CustomerFinancialAccessScope) -> PortfolioRiskProjection:
        self.calls["get_portfolio_risk"] += 1
        self._require(scope, ProductFinancialSurface.PORTFOLIO)
        return PortfolioRiskProjection(
            status=FinancialProjectionStatus.READY,
            provenance=self._provenance("portfolio-risk"),
            warnings=(SYNTHETIC_WARNING,),
            portfolio_ref="synthetic-portfolio-1",
            risk_state="NO_REAL_EXPOSURE",
            concentration_state="SYNTHETIC_CASH_ONLY",
            drawdown=Decimal("0"),
            source_status=FinancialSourceStatus.SYNTHETIC,
        )

    def get_trading_coach_summary(self, scope: CustomerFinancialAccessScope) -> TradingCoachProjection:
        self.calls["get_trading_coach_summary"] += 1
        self._require(scope, ProductFinancialSurface.COACH)
        return TradingCoachProjection(
            status=FinancialProjectionStatus.READY,
            provenance=self._provenance("coach"),
            warnings=(SYNTHETIC_WARNING,),
            summary="Synthetic coaching sample for layout validation.",
            strengths=("Risk limit shown before any action.",),
            review_items=("Confirm source freshness before relying on a market view.",),
            source_status=FinancialSourceStatus.SYNTHETIC,
        )

    def get_shadow_medar_summary(self, scope: CustomerFinancialAccessScope) -> ShadowMedarProjection:
        self.calls["get_shadow_medar_summary"] += 1
        self._require(scope, ProductFinancialSurface.SHADOW_MEDAR)
        return ShadowMedarProjection(
            status=FinancialProjectionStatus.READY,
            provenance=self._provenance("shadow-medar"),
            warnings=(SYNTHETIC_WARNING,),
            summary="Synthetic shadow analysis; no action or advice authority.",
            confidence=0.5,
            evidence=("Synthetic NQ range fixture", "Synthetic portfolio has no exposure"),
            source_status=FinancialSourceStatus.SYNTHETIC,
        )

    def get_financial_alerts(self, scope: CustomerFinancialAccessScope) -> FinancialAlertCollection:
        self.calls["get_financial_alerts"] += 1
        self._require(scope, ProductFinancialSurface.OVERVIEW)
        return FinancialAlertCollection(
            status=FinancialProjectionStatus.READY,
            provenance=self._provenance("alerts"),
            warnings=(SYNTHETIC_WARNING,),
            alerts=(self._alert(),),
            source_status=FinancialSourceStatus.SYNTHETIC,
        )

    def get_daily_financial_snapshot(self, scope: CustomerFinancialAccessScope) -> DailyFinancialSnapshot:
        self.calls["get_daily_financial_snapshot"] += 1
        self._require(scope, ProductFinancialSurface.OVERVIEW)
        return DailyFinancialSnapshot(
            status=FinancialProjectionStatus.READY,
            provenance=self._provenance("daily"),
            warnings=(SYNTHETIC_WARNING,),
            headline="Synthetic daily financial snapshot for local UI testing.",
            trading=self._trading(scope, "NQ"),
            portfolio=self.get_portfolio_summary(scope),
            coach=self.get_trading_coach_summary(scope),
            shadow_medar=self.get_shadow_medar_summary(scope),
            alerts=(self._alert(),),
            source_status=FinancialSourceStatus.SYNTHETIC,
        )
