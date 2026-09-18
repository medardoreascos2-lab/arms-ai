"""Operational admission composition; delegates policy to existing authorities.

TradeLifecycleServiceV2 owns the decision. This object owns its runtime market
bindings and an execution scope, not a second risk or freshness implementation.
Historical replay lifecycles have separate ledgers and do not bind this object.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone

from backend.services.runtime_quote_authority_v2 import RuntimeQuoteAuthorityV2
from backend.services.runtime_spread_authority_v2 import RuntimeSpreadAuthorityV2
from backend.services.spread_authority_v2 import SpreadAuthorityV2
from backend.services.certified_market_hours_data_lifecycle_v2 import CertifiedMarketHoursDataLifecycleV2
from backend.services.certified_market_hours_runtime_provider_v2 import CertifiedMarketHoursRuntimeProviderV2
from backend.services.certified_economic_news_data_lifecycle_v2 import CertifiedEconomicNewsDataLifecycleV2
from backend.execution.exposure_manager_v2 import ExposureManagerV2
from backend.execution.portfolio_risk_engine_v2 import PortfolioRiskEngineV2
from backend.execution.order_validation_engine_v2 import OrderValidationEngineV2


class RuntimeAdmissionV2:
    def __init__(self, *, settings):
        self.settings = settings
        self.clock = lambda: datetime.now(timezone.utc)
        self.quote_authority = RuntimeQuoteAuthorityV2()
        self.spread_authority = SpreadAuthorityV2()
        self.runtime_spread_authority = RuntimeSpreadAuthorityV2(
            quote_authority=self.quote_authority, spread_authority=self.spread_authority,
            maximum_quote_age_seconds=settings.maximum_quote_age_seconds)
        self.market_hours_lifecycle = CertifiedMarketHoursDataLifecycleV2()
        self._unavailable_market_hours = CertifiedMarketHoursRuntimeProviderV2()
        self.news_lifecycle = CertifiedEconomicNewsDataLifecycleV2()
        if settings.certified_market_hours_path is not None:
            self.market_hours_lifecycle.activate_from_file(file_path=settings.certified_market_hours_path)
        if settings.certified_economic_news_path is not None:
            self.news_lifecycle.activate_from_file(file_path=settings.certified_economic_news_path)
        self._executing = ContextVar("runtime_admitted_execution", default=False)

    @property
    def market_hours_provider(self):
        return self.market_hours_lifecycle.get_active_provider() or self._unavailable_market_hours

    @property
    def news_provider(self):
        return self.news_lifecycle.get_active_provider()

    def validate_market(self, *, symbol):
        # One timestamp and one quote snapshot. Never trust caller market flags,
        # current_price, or a request-supplied timestamp as runtime evidence.
        now = self.clock()
        quote = self.runtime_spread_authority.get_current_quote(symbol=symbol, now=now)
        spread = self.spread_authority.resolve_spread_points(
            symbol=quote["symbol"], bid=quote["bid"], ask=quote["ask"])
        if spread > self.settings.maximum_spread_points:
            raise ValueError("runtime spread exceeds configured maximum")
        if not self.market_hours_provider.get_market_hours_service().is_market_open(symbol=symbol, timestamp=now):
            raise ValueError("runtime market hours unavailable or closed")
        if self.news_provider.get_economic_news_authority().is_news_blocked(symbol=symbol, timestamp=now):
            raise ValueError("runtime economic news unavailable or blocked")
        return quote

    @contextmanager
    def _execution_scope(self):
        token = self._executing.set(True)
        try:
            yield
        finally:
            self._executing.reset(token)

    def require_execution_scope(self):
        if not self._executing.get():
            from backend.services.durable_execution_state_v2 import AccountAdmissionRejected
            raise AccountAdmissionRejected("canonical_runtime_admission_required")


def bind_runtime_admission(lifecycle, *, settings, policy):
    """Bind once during operational composition; preserve explicitly injected guards."""
    lifecycle._runtime_admission_required = True
    if getattr(lifecycle, "runtime_admission_v2", None) is None:
        lifecycle.runtime_admission_v2 = RuntimeAdmissionV2(settings=settings)
    if lifecycle.exposure_manager_v2 is None:
        lifecycle.exposure_manager_v2 = ExposureManagerV2(
            maximum_total_open_risk=policy.maximum_total_open_risk,
            maximum_symbol_open_risk=policy.maximum_symbol_open_risk,
            maximum_total_contracts=None, maximum_symbol_contracts=None)
    if lifecycle.portfolio_risk_engine_v2 is None:
        lifecycle.portfolio_risk_engine_v2 = PortfolioRiskEngineV2(
            maximum_total_open_risk=policy.maximum_portfolio_open_risk,
            maximum_floating_loss=policy.maximum_portfolio_floating_loss,
            maximum_long_risk=policy.maximum_portfolio_long_risk,
            maximum_short_risk=policy.maximum_portfolio_short_risk,
            maximum_symbol_risk=policy.maximum_portfolio_symbol_risk)
    if lifecycle.order_validation_engine_v2 is None:
        lifecycle.order_validation_engine_v2 = OrderValidationEngineV2(
            minimum_reward_risk_ratio=settings.minimum_reward_risk_ratio,
            minimum_stop_points=settings.minimum_stop_points,
            maximum_stop_points=settings.maximum_stop_points,
            allowed_symbols={"NQ", "MNQ", "ES", "MES"})
    return lifecycle.runtime_admission_v2
