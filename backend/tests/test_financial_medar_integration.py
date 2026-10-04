"""F112A: MEDAR consumes structured financial inputs with unchanged tools."""

from backend.financial.medar_integration import MEDARFinancialBundle
from backend.financial.scorecard import CompanyScorecard
from backend.medar.agents import FinancialResearchAgent
from backend.medar.financial_router import FinancialProduct, route_financial_task


def test_financial_agent_consumes_evidence_without_action_or_new_tools():
    agent = FinancialResearchAgent()
    before = agent.contract.allowed_tools
    bundle = MEDARFinancialBundle(("synthetic:filing",),
                                  company_scorecard=CompanyScorecard("NASDAQ:TEST", "2026-Q2"))
    output = agent.analyze_financial("synthetic:task", bundle)
    assert "stocks" in output.summary
    assert output.evidence == ("synthetic:filing",)
    assert output.confidence == 0.0
    assert not output.action_performed
    assert agent.contract.allowed_tools == before
    assert agent.contract.real_world_action_authority is False


def test_financial_router_points_to_real_modules_without_execution():
    for product in (FinancialProduct.STOCK, FinancialProduct.ETF, FinancialProduct.CRYPTO,
                    FinancialProduct.PORTFOLIO, FinancialProduct.ARBITRAGE,
                    FinancialProduct.TRADING_COACH, FinancialProduct.SHADOW_MEDAR):
        route = route_financial_task(product)
        assert route.target_module.startswith("backend.financial.")
        assert not route.execution_authority
