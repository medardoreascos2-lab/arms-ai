"""R81C MEDAR domain router tests."""

from backend.medar.capabilities import default_capability_registry
from backend.medar.domain_router import DomainRouteStatus, DomainRouter
from backend.medar.intent import IntentClassification
from backend.medar.request import CognitiveDomain


def _classification(domains, confidence=0.9):
    return IntentClassification(domains[0], domains, confidence, (), len(domains) > 1)


def test_routes_single_domain_to_registered_capability():
    route = DomainRouter(default_capability_registry()).route(
        _classification((CognitiveDomain.CODING,))
    )

    assert route.status is DomainRouteStatus.SINGLE_DOMAIN
    assert tuple(item.capability_id for item in route.capabilities) == ("code_analysis",)
    assert route.action_authorized is False


def test_routes_supported_multi_domain_without_conflating_capabilities():
    route = DomainRouter(default_capability_registry()).route(
        _classification((CognitiveDomain.WEB_RESEARCH, CognitiveDomain.FINANCIAL))
    )

    assert route.status is DomainRouteStatus.MULTI_DOMAIN
    assert tuple(item.capability_id for item in route.capabilities) == (
        "web_search",
        "financial_analysis",
    )
    assert route.action_authorized is False


def test_low_confidence_route_requests_clarification_without_capability():
    route = DomainRouter(default_capability_registry()).route(
        _classification((CognitiveDomain.BUSINESS, CognitiveDomain.LIFE_ADVICE), confidence=0.2)
    )

    assert route.status is DomainRouteStatus.AMBIGUOUS
    assert route.capabilities == ()


def test_unknown_never_maps_to_action_capable_domain():
    route = DomainRouter(default_capability_registry()).route(
        _classification((CognitiveDomain.UNKNOWN,), confidence=0.0)
    )

    assert route.status is DomainRouteStatus.UNSUPPORTED
    assert route.capabilities == ()
    assert route.action_authorized is False
