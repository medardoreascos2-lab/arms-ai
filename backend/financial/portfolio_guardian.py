"""Advisory portfolio guardian; absent evidence is reported as unknown."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from backend.financial.portfolio_risk import PortfolioRiskReport


class GuardianCode(str, Enum):
    CONCENTRATION_HIGH = "CONCENTRATION_HIGH"
    CORRELATION_HIGH = "CORRELATION_HIGH"
    DRAWDOWN_RISK = "DRAWDOWN_RISK"
    LIQUIDITY_RISK = "LIQUIDITY_RISK"
    EVENT_RISK = "EVENT_RISK"
    SECTOR_OVERWEIGHT = "SECTOR_OVERWEIGHT"


@dataclass(frozen=True)
class GuardianThresholds:
    concentration: Decimal
    correlation: Decimal
    drawdown: Decimal
    liquidity_days: Decimal
    sector_weight: Decimal

    def __post_init__(self) -> None:
        for name in ("concentration", "correlation", "drawdown", "liquidity_days", "sector_weight"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise ValueError(f"{name} threshold must be positive and finite")


@dataclass(frozen=True)
class GuardianAlert:
    code: GuardianCode
    observed: Decimal | str
    threshold: Decimal | None
    advisory_only: bool = True


@dataclass(frozen=True)
class GuardianReport:
    alerts: tuple[GuardianAlert, ...]
    unknown_checks: tuple[GuardianCode, ...]
    advisory_only: bool = True


def guard_portfolio(
    risk: PortfolioRiskReport,
    thresholds: GuardianThresholds,
    *,
    event_risk: str | None = None,
    event_check_complete: bool = False,
) -> GuardianReport:
    alerts: list[GuardianAlert] = []
    unknown: list[GuardianCode] = []
    checks = (
        (GuardianCode.CONCENTRATION_HIGH, risk.concentration, thresholds.concentration),
        (GuardianCode.CORRELATION_HIGH, risk.max_pair_correlation, thresholds.correlation),
        (GuardianCode.DRAWDOWN_RISK, risk.max_drawdown, thresholds.drawdown),
        (GuardianCode.LIQUIDITY_RISK, risk.liquidity_days, thresholds.liquidity_days),
    )
    for code, observed, limit in checks:
        if observed is None:
            unknown.append(code)
        elif observed > limit:
            alerts.append(GuardianAlert(code, observed, limit))
    if risk.sector_exposure is None:
        unknown.append(GuardianCode.SECTOR_OVERWEIGHT)
    else:
        for sector, weight in risk.sector_exposure.items():
            if weight > thresholds.sector_weight:
                alerts.append(GuardianAlert(GuardianCode.SECTOR_OVERWEIGHT, f"{sector}:{weight}", thresholds.sector_weight))
    if event_risk is not None:
        if not event_risk.strip():
            raise ValueError("event_risk must be nonblank")
        alerts.append(GuardianAlert(GuardianCode.EVENT_RISK, event_risk, None))
    elif not event_check_complete:
        unknown.append(GuardianCode.EVENT_RISK)
    return GuardianReport(tuple(alerts), tuple(unknown))
