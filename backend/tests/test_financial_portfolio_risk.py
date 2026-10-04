"""F102B: portfolio risk stays unknown when source inputs are incomplete."""

from datetime import datetime, timezone
from decimal import Decimal

from backend.financial.asset import AssetType
from backend.financial.portfolio import PortfolioPosition, PortfolioSnapshot
from backend.financial.portfolio_risk import PortfolioRiskEvidence, analyze_portfolio_risk

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def portfolio():
    return PortfolioSnapshot(
        "synthetic:p", "USD", "synthetic:positions", NOW,
        (
            PortfolioPosition("A", AssetType.STOCK, "USD", Decimal("1"), Decimal("50"), Decimal("60"), sector="Tech"),
            PortfolioPosition("B", AssetType.ETF, "USD", Decimal("1"), Decimal("40"), Decimal("40"), sector="Broad"),
        ),
    )


def test_risk_calculates_only_evidenced_metrics():
    report = analyze_portfolio_risk(portfolio(), PortfolioRiskEvidence())
    assert report.concentration == Decimal("0.6")
    assert report.sector_exposure["Tech"] == Decimal("0.6")
    assert report.asset_class_exposure["ETF"] == Decimal("0.4")
    assert report.volatility is None
    assert report.beta is None
    assert report.max_drawdown is None
    evidence = PortfolioRiskEvidence(
        volatility={"A": Decimal("0.2"), "B": Decimal("0.1")},
        beta={"A": Decimal("1.2"), "B": Decimal("1")},
        correlation={("A", "B"): Decimal("0.5")},
        average_daily_volume={"A": Decimal("10"), "B": Decimal("20")},
        equity_path=(Decimal("100"), Decimal("90"), Decimal("95")),
    )
    complete = analyze_portfolio_risk(portfolio(), evidence)
    assert complete.volatility is not None
    assert complete.max_pair_correlation == Decimal("0.5")
    assert complete.max_drawdown == Decimal("0.1")
    assert complete.beta == Decimal("1.12")
    assert complete.liquidity_days == Decimal("0.1")
