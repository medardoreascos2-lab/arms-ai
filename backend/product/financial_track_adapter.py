"""Future seam for published Financial Intelligence read contracts.

No Financial Track implementation is imported here. Integration remains pending until
a stable public contract client and mapping specification are supplied.
"""

from __future__ import annotations

from typing import Protocol

from backend.product.financial_access import CustomerFinancialAccessScope
from backend.product.financial_models import FinancialReadStatus


class PublishedFinancialContractClient(Protocol):
    """Marker for a future read-only client backed by published public contracts."""

    def readiness(self) -> FinancialReadStatus: ...


class FinancialTrackIntegrationPending(RuntimeError):
    pass


class PendingFinancialTrackAdapter:
    """Product provider-shaped seam that always fails closed while unbound."""

    def readiness(self) -> FinancialReadStatus:
        return FinancialReadStatus.INTEGRATION_PENDING

    @staticmethod
    def _pending(scope: CustomerFinancialAccessScope):
        if not isinstance(scope, CustomerFinancialAccessScope):
            raise PermissionError("trusted customer financial scope required")
        raise FinancialTrackIntegrationPending(
            "published Financial Intelligence contract adapter is not connected"
        )

    get_trading_summary = _pending
    get_nq_summary = _pending
    get_mnq_summary = _pending
    get_portfolio_summary = _pending
    get_portfolio_risk = _pending
    get_trading_coach_summary = _pending
    get_shadow_medar_summary = _pending
    get_financial_alerts = _pending
    get_daily_financial_snapshot = _pending
