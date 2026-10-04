"""Provider-neutral Product financial read contract.

The interface intentionally contains observations only. Implementations cannot gain
broker, account, portfolio, PAPER, or LIVE mutation authority through this contract.
"""

from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

from backend.product.financial_access import CustomerFinancialAccessScope

if TYPE_CHECKING:
    from backend.product.financial_models import (
        DailyFinancialSnapshot,
        FinancialAlertCollection,
        PortfolioRiskProjection,
        PortfolioSummaryProjection,
        ShadowMedarProjection,
        TradingCoachProjection,
        TradingSummaryProjection,
    )


class ProductFinancialReadProvider(Protocol):
    def get_trading_summary(
        self, scope: CustomerFinancialAccessScope
    ) -> TradingSummaryProjection: ...

    def get_nq_summary(
        self, scope: CustomerFinancialAccessScope
    ) -> TradingSummaryProjection: ...

    def get_mnq_summary(
        self, scope: CustomerFinancialAccessScope
    ) -> TradingSummaryProjection: ...

    def get_portfolio_summary(
        self, scope: CustomerFinancialAccessScope
    ) -> PortfolioSummaryProjection: ...

    def get_portfolio_risk(
        self, scope: CustomerFinancialAccessScope
    ) -> PortfolioRiskProjection: ...

    def get_trading_coach_summary(
        self, scope: CustomerFinancialAccessScope
    ) -> TradingCoachProjection: ...

    def get_shadow_medar_summary(
        self, scope: CustomerFinancialAccessScope
    ) -> ShadowMedarProjection: ...

    def get_financial_alerts(
        self, scope: CustomerFinancialAccessScope
    ) -> FinancialAlertCollection: ...

    def get_daily_financial_snapshot(
        self, scope: CustomerFinancialAccessScope
    ) -> DailyFinancialSnapshot: ...
