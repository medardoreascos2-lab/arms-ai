"""Structured, nonexecuting MEDAR financial input integration."""

from dataclasses import dataclass

from backend.financial.arbitrage_ranking import RankingResult
from backend.financial.crypto_scanner import CryptoScanResult
from backend.financial.portfolio_risk import PortfolioRiskReport
from backend.financial.scorecard import CompanyScorecard
from backend.financial.shadow_comparison import UserShadowComparison
from backend.financial.trading_coach import TradingCoachSummary
from backend.medar.agent_contract import AgentOutput


@dataclass(frozen=True)
class MEDARFinancialBundle:
    evidence_references: tuple[str, ...]
    company_scorecard: CompanyScorecard | None = None
    portfolio_risk: PortfolioRiskReport | None = None
    crypto_scan: CryptoScanResult | None = None
    arbitrage_ranking: RankingResult | None = None
    trading_coach: TradingCoachSummary | None = None
    shadow_comparison: UserShadowComparison | None = None

    def __post_init__(self) -> None:
        values = (
            self.company_scorecard, self.portfolio_risk, self.crypto_scan,
            self.arbitrage_ranking, self.trading_coach, self.shadow_comparison,
        )
        expected = (
            CompanyScorecard, PortfolioRiskReport, CryptoScanResult,
            RankingResult, TradingCoachSummary, UserShadowComparison,
        )
        if any(value is not None and not isinstance(value, kind) for value, kind in zip(values, expected)):
            raise TypeError("financial bundle inputs must use validated analysis models")
        if not any(value is not None for value in values):
            raise ValueError("financial bundle requires at least one analysis input")
        if not self.evidence_references or any(not ref.strip() for ref in self.evidence_references):
            raise ValueError("financial bundle requires explicit evidence references")
        object.__setattr__(self, "evidence_references", tuple(self.evidence_references))


def synthesize_financial_inputs(
    agent_id: str, task_id: str, bundle: MEDARFinancialBundle,
) -> AgentOutput:
    names = (
        ("stocks", bundle.company_scorecard),
        ("portfolio", bundle.portfolio_risk),
        ("crypto", bundle.crypto_scan),
        ("arbitrage", bundle.arbitrage_ranking),
        ("trading_coach", bundle.trading_coach),
        ("shadow_medar", bundle.shadow_comparison),
    )
    available = ",".join(name for name, value in names if value is not None)
    return AgentOutput(
        agent_id, task_id, f"Structured financial analysis inputs available: {available}",
        bundle.evidence_references, ("ANALYSIS_ONLY", "NO_EXTERNAL_ACTION", "NO_RECOMMENDATION"),
        0.0,
    )
