"""Fail-closed domain and capability routing for MEDAR."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.capabilities import Capability, CapabilityRegistry
from backend.medar.intent import IntentClassification
from backend.medar.request import CognitiveDomain


class DomainRouteStatus(str, Enum):
    SINGLE_DOMAIN = "SINGLE_DOMAIN"
    MULTI_DOMAIN = "MULTI_DOMAIN"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class DomainRoute:
    status: DomainRouteStatus
    domains: tuple[CognitiveDomain, ...]
    capabilities: tuple[Capability, ...]
    reasons: tuple[str, ...]
    action_authorized: bool = False


class DomainRouter:
    def __init__(self, registry: CapabilityRegistry, *, ambiguity_threshold: float = 0.6):
        if not 0.0 <= ambiguity_threshold <= 1.0:
            raise ValueError("ambiguity threshold must be between zero and one")
        self._registry = registry
        self._threshold = ambiguity_threshold

    def route(self, classification: IntentClassification) -> DomainRoute:
        domains = tuple(dict.fromkeys(classification.domains))
        if not domains or CognitiveDomain.UNKNOWN in domains:
            return DomainRoute(
                DomainRouteStatus.UNSUPPORTED,
                domains or (CognitiveDomain.UNKNOWN,),
                (),
                ("UNKNOWN_DOMAIN_REQUIRES_CLARIFICATION",),
            )
        if classification.confidence < self._threshold:
            return DomainRoute(
                DomainRouteStatus.AMBIGUOUS,
                domains,
                (),
                ("CLASSIFICATION_CONFIDENCE_BELOW_THRESHOLD",),
            )
        capabilities = tuple(
            capability
            for domain in domains
            for capability in self._registry.for_domain(domain)
        )
        missing = tuple(domain.value for domain in domains if not self._registry.for_domain(domain))
        if missing:
            return DomainRoute(
                DomainRouteStatus.UNSUPPORTED,
                domains,
                (),
                tuple(f"NO_CAPABILITY:{domain}" for domain in missing),
            )
        status = DomainRouteStatus.SINGLE_DOMAIN if len(domains) == 1 else DomainRouteStatus.MULTI_DOMAIN
        return DomainRoute(status, domains, capabilities, ("CAPABILITY_MATCHED",))
