"""Safe initial MEDAR agents backed only by local deterministic behavior."""

from backend.medar.agent_contract import AgentContract, AgentInput, AgentOutput
from backend.medar.capabilities import MemoryPermission
from backend.medar.model_policy import ModelAccessPolicy
from backend.medar.request import CognitiveDomain, RiskClass


class BoundedAnalysisAgent:
    contract: AgentContract

    def analyze(self, input_data: AgentInput) -> AgentOutput:
        if not input_data.goal.strip():
            raise ValueError("agent goal is required")
        return AgentOutput(
            self.contract.agent_id,
            input_data.task_id,
            f"{self.contract.agent_id} prepared a bounded analysis for: {input_data.goal}",
            input_data.evidence,
            ("LOCAL_DETERMINISTIC_AGENT_NO_EXTERNAL_MODEL",),
            0.5 if input_data.evidence else 0.3,
        )


class GeneralAssistantAgent(BoundedAnalysisAgent):
    contract = AgentContract(
        "general-assistant",
        CognitiveDomain.GENERAL,
        ("general_analysis", "document_analysis", "image_request", "voice_request"),
        ("calculator", "document_reader_stub"),
        (MemoryPermission.READ, MemoryPermission.PROPOSE_WRITE),
        RiskClass.MODERATE,
        ModelAccessPolicy.LOCAL_FIRST,
    )


class WebResearchAgent(BoundedAnalysisAgent):
    contract = AgentContract(
        "web-research",
        CognitiveDomain.WEB_RESEARCH,
        ("web_search",),
        ("web_search_stub",),
        (MemoryPermission.NONE,),
        RiskClass.MODERATE,
        ModelAccessPolicy.REMOTE_ALLOWED,
    )

    def synthesize(self, findings, sources):
        from backend.medar.research_synthesis import synthesize_research

        return synthesize_research(findings, sources)


class CodingAgent(BoundedAnalysisAgent):
    contract = AgentContract(
        "coding",
        CognitiveDomain.CODING,
        ("code_analysis",),
        ("code_analysis_stub",),
        (MemoryPermission.READ,),
        RiskClass.MODERATE,
        ModelAccessPolicy.LOCAL_FIRST,
    )


class FinancialResearchAgent(BoundedAnalysisAgent):
    contract = AgentContract(
        "financial-research",
        CognitiveDomain.FINANCIAL,
        ("financial_analysis", "trading_analysis", "portfolio_analysis", "crypto_market_scan"),
        ("financial_analysis_stub", "web_search_stub"),
        (MemoryPermission.READ,),
        RiskClass.HIGH,
        ModelAccessPolicy.LOCAL_FIRST,
    )


class BusinessAdvisorAgent(BoundedAnalysisAgent):
    contract = AgentContract(
        "business-advisor",
        CognitiveDomain.BUSINESS,
        ("business_analysis", "marketing_analysis"),
        ("web_search_stub",),
        (MemoryPermission.READ,),
        RiskClass.MODERATE,
        ModelAccessPolicy.LOCAL_FIRST,
    )


class LifeDecisionAgent(BoundedAnalysisAgent):
    contract = AgentContract(
        "life-decision",
        CognitiveDomain.LIFE_ADVICE,
        ("life_decision_analysis",),
        (),
        (MemoryPermission.READ, MemoryPermission.PROPOSE_WRITE),
        RiskClass.MODERATE,
        ModelAccessPolicy.LOCAL_ONLY,
    )


class RositaKnowledgeAgent(BoundedAnalysisAgent):
    contract = AgentContract(
        "rosita-knowledge",
        CognitiveDomain.ROSITA,
        ("rosita_knowledge",),
        ("memory_lookup_stub",),
        (MemoryPermission.READ,),
        RiskClass.HIGH,
        ModelAccessPolicy.LOCAL_ONLY,
    )

    def respond_health(self, items, summary, operations):
        from backend.medar.rosita_boundary import build_rosita_health_response

        return build_rosita_health_response(items, summary, operations)


def initial_agents() -> tuple[BoundedAnalysisAgent, ...]:
    return (
        GeneralAssistantAgent(),
        WebResearchAgent(),
        CodingAgent(),
        FinancialResearchAgent(),
        BusinessAdvisorAgent(),
        LifeDecisionAgent(),
        RositaKnowledgeAgent(),
    )
