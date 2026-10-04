"""Capability contracts and immutable registry for MEDAR routing."""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from backend.medar.request import CognitiveDomain, RiskClass


class MemoryPermission(str, Enum):
    NONE = "NONE"
    READ = "READ"
    PROPOSE_WRITE = "PROPOSE_WRITE"


@dataclass(frozen=True)
class Capability:
    capability_id: str
    domain: CognitiveDomain
    description: str
    risk_class: RiskClass
    tool_requirements: tuple[str, ...]
    memory_permissions: tuple[MemoryPermission, ...]
    confirmation_required: bool
    execution_authority: bool = False

    def __post_init__(self) -> None:
        if not self.capability_id.strip() or not self.description.strip():
            raise ValueError("capability identity and description are required")
        if len(set(self.tool_requirements)) != len(self.tool_requirements):
            raise ValueError("tool requirements must be unique")
        if len(set(self.memory_permissions)) != len(self.memory_permissions):
            raise ValueError("memory permissions must be unique")
        if self.risk_class in {RiskClass.HIGH, RiskClass.CRITICAL} and not self.confirmation_required:
            raise ValueError("high-risk capability requires confirmation")


class CapabilityRegistry:
    def __init__(self, capabilities: tuple[Capability, ...]):
        entries: dict[str, Capability] = {}
        for capability in capabilities:
            if capability.capability_id in entries:
                raise ValueError("duplicate capability id")
            entries[capability.capability_id] = capability
        self._entries: Mapping[str, Capability] = MappingProxyType(entries)

    def get(self, capability_id: str) -> Capability:
        try:
            return self._entries[capability_id]
        except KeyError as exc:
            raise KeyError(f"unsupported capability: {capability_id}") from exc

    def for_domain(self, domain: CognitiveDomain) -> tuple[Capability, ...]:
        return tuple(item for item in self._entries.values() if item.domain is domain)

    @property
    def capabilities(self) -> tuple[Capability, ...]:
        return tuple(self._entries.values())


def default_capability_registry() -> CapabilityRegistry:
    specs = (
        ("general_analysis", CognitiveDomain.GENERAL, "Answer bounded general questions", RiskClass.LOW, (), (MemoryPermission.READ,), False),
        ("web_search", CognitiveDomain.WEB_RESEARCH, "Collect current web evidence", RiskClass.MODERATE, ("web_search_stub",), (MemoryPermission.NONE,), False),
        ("code_analysis", CognitiveDomain.CODING, "Inspect code within an allowed scope", RiskClass.MODERATE, ("code_analysis_stub",), (MemoryPermission.READ,), False),
        ("financial_analysis", CognitiveDomain.FINANCIAL, "Analyze financial evidence without execution", RiskClass.HIGH, ("financial_analysis_stub",), (MemoryPermission.READ,), True),
        ("trading_analysis", CognitiveDomain.TRADING, "Analyze NQ or MNQ without execution", RiskClass.HIGH, ("financial_analysis_stub",), (MemoryPermission.READ,), True),
        ("portfolio_analysis", CognitiveDomain.PORTFOLIO, "Analyze portfolio risk without changing holdings", RiskClass.HIGH, ("financial_analysis_stub",), (MemoryPermission.READ,), True),
        ("crypto_market_scan", CognitiveDomain.CRYPTO, "Compare crypto market observations", RiskClass.HIGH, ("financial_analysis_stub",), (MemoryPermission.NONE,), True),
        ("business_analysis", CognitiveDomain.BUSINESS, "Compare business options and KPIs", RiskClass.MODERATE, (), (MemoryPermission.READ,), False),
        ("marketing_analysis", CognitiveDomain.MARKETING, "Analyze marketing evidence", RiskClass.MODERATE, ("web_search_stub",), (MemoryPermission.READ,), False),
        ("life_decision_analysis", CognitiveDomain.LIFE_ADVICE, "Support reversible personal decisions", RiskClass.MODERATE, (), (MemoryPermission.READ,), False),
        ("rosita_knowledge", CognitiveDomain.ROSITA, "Retrieve labeled Rosita knowledge", RiskClass.HIGH, ("memory_lookup_stub",), (MemoryPermission.READ,), True),
        ("computer_action_proposal", CognitiveDomain.COMPUTER_ACTION, "Propose a permission-gated computer action", RiskClass.CRITICAL, (), (MemoryPermission.NONE,), True),
        ("document_analysis", CognitiveDomain.DOCUMENT, "Read an approved document", RiskClass.MODERATE, ("document_reader_stub",), (MemoryPermission.NONE,), False),
        ("image_request", CognitiveDomain.IMAGE, "Describe a future image request", RiskClass.MODERATE, (), (MemoryPermission.NONE,), False),
        ("voice_request", CognitiveDomain.VOICE, "Describe a future voice request", RiskClass.MODERATE, (), (MemoryPermission.NONE,), False),
    )
    return CapabilityRegistry(tuple(Capability(*spec) for spec in specs))
