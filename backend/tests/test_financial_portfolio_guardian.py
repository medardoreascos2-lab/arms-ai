"""F102C: guardian alerts are advisory and unknown checks stay visible."""

from decimal import Decimal

from backend.financial.portfolio_guardian import (
    GuardianCode, GuardianThresholds, guard_portfolio,
)
from backend.financial.portfolio_risk import PortfolioRiskReport


def test_guardian_flags_known_risks_and_does_not_pass_unknowns():
    risk = PortfolioRiskReport(
        Decimal("0.7"), {"Tech": Decimal("0.7")}, {"STOCK": Decimal("0.7")},
        None, None, None, None, None, Decimal("0.7"),
    )
    limits = GuardianThresholds(Decimal("0.5"), Decimal("0.8"), Decimal("0.2"),
                                 Decimal("2"), Decimal("0.6"))
    report = guard_portfolio(risk, limits)
    assert {a.code for a in report.alerts} == {
        GuardianCode.CONCENTRATION_HIGH, GuardianCode.SECTOR_OVERWEIGHT,
    }
    assert GuardianCode.CORRELATION_HIGH in report.unknown_checks
    assert GuardianCode.EVENT_RISK in report.unknown_checks
    assert report.advisory_only and all(a.advisory_only for a in report.alerts)
