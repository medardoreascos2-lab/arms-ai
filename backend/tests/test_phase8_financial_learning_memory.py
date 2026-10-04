"""R121D validates financial learning records remain evidence-bound and nonexecuting."""

from datetime import datetime, timezone
from decimal import Decimal

from backend.medar.arbitrage_outcome_memory import ArbitrageOutcomeMemory, PaperResultMode
from backend.medar.futures_research_memory import FuturesInstrument, FuturesResearchMemory, ResearchObservationMode
from backend.medar.portfolio_memory import PortfolioEvidenceMode, PortfolioMemory

NOW = datetime(2026, 10, 4, 21, 30, tzinfo=timezone.utc)


def test_financial_learning_preserves_dataset_cost_and_risk_evidence_without_authority():
    futures = FuturesResearchMemory(
        FuturesInstrument.NQ, "tenant-a", "owner-a", "session-a",
        "synthetic-study:nq-1", "synthetic-dataset:nq-bars-1", ResearchObservationMode.SYNTHETIC_TEST,
        "synthetic range", "synthetic liquidity sweep", "hold", "no synthetic order",
        "risk gate remained closed", "synthetic bar trace", NOW,
    )
    portfolio = PortfolioMemory(
        "tenant-a", "owner-a", "session-a", "synthetic-portfolio-a",
        "synthetic-study:portfolio-1", "synthetic-dataset:positions-1", PortfolioEvidenceMode.SYNTHETIC_TEST,
        "synthetic diversification thesis", "synthetic concentration risk", "hold synthetic weights",
        "propose no change", "no portfolio mutation", NOW,
    )
    arbitrage = ArbitrageOutcomeMemory(
        "tenant-a", "owner-a", "session-a", "synthetic-scan:arb-1",
        "synthetic-dataset:quotes-1", "synthetic-opportunity:arb-1", "USD",
        Decimal("10.00"), Decimal("3.00"), Decimal("2.50"), Decimal("1.00"), Decimal("4.00"),
        PaperResultMode.NO_PAPER_FILL, "no paper fill observed", NOW,
    )

    assert futures.dataset_reference == "synthetic-dataset:nq-bars-1"
    assert futures.decision == "hold" and futures.result == "no synthetic order"
    assert portfolio.dataset_reference == "synthetic-dataset:positions-1"
    assert portfolio.rebalance_proposal == "propose no change" and portfolio.outcome == "no portfolio mutation"
    assert arbitrage.net_edge == Decimal("-0.50") and not arbitrage.profitable_on_stated_costs
    assert futures.session_only and portfolio.session_only and arbitrage.session_only
    assert not any((
        futures.broker_authority, futures.paper_execution_authority, futures.live_execution_authority,
        portfolio.portfolio_mutation_authority, portfolio.trading_authority,
        arbitrage.exchange_execution_authority, arbitrage.paper_execution_authority, arbitrage.live_execution_authority,
    ))
