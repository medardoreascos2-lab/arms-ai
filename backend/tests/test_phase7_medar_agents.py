"""R85B initial safe MEDAR agent tests."""

from backend.medar.agent_contract import AgentInput
from backend.medar.agents import initial_agents


def test_initial_agent_set_is_complete_and_has_no_real_world_authority():
    agents = initial_agents()

    assert tuple(agent.contract.agent_id for agent in agents) == (
        "general-assistant",
        "web-research",
        "coding",
        "financial-research",
        "business-advisor",
        "life-decision",
        "rosita-knowledge",
    )
    assert all(agent.contract.real_world_action_authority is False for agent in agents)


def test_agents_return_explicit_bounded_local_output():
    for agent in initial_agents():
        output = agent.analyze(
            AgentInput("req-1", f"task-{agent.contract.agent_id}", "analyze supplied evidence", ("evidence-1",))
        )
        assert output.action_performed is False
        assert output.evidence == ("evidence-1",)
        assert output.warnings == ("LOCAL_DETERMINISTIC_AGENT_NO_EXTERNAL_MODEL",)
        assert output.confidence == 0.5


def test_financial_agent_covers_analysis_seams_without_execution():
    financial = next(agent for agent in initial_agents() if agent.contract.agent_id == "financial-research")

    assert set(financial.contract.capabilities) == {
        "financial_analysis",
        "trading_analysis",
        "portfolio_analysis",
        "crypto_market_scan",
    }
    assert financial.contract.real_world_action_authority is False
