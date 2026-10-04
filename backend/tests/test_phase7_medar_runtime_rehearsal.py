"""R95B synthetic end-to-end cognitive runtime rehearsal."""

import pytest

from backend.medar.core import default_cognitive_core
from backend.medar.domain_router import DomainRouteStatus
from backend.medar.request import (
    CognitiveDomain, CognitiveRequest, RiskClass, TimeSensitivity, normalize_user_input,
)


def _request(index, text):
    return CognitiveRequest(
        f"request-{index}", "conversation", "rehearse", text, normalize_user_input(text),
        CognitiveDomain.UNKNOWN, RiskClass.LOW, (), TimeSensitivity.STATIC,
    )


@pytest.mark.parametrize(
    "text,expected",
    (
        ("Explain this general question", CognitiveDomain.GENERAL),
        ("Research the latest web sources", CognitiveDomain.WEB_RESEARCH),
        ("Inspect this code repository bug", CognitiveDomain.CODING),
        ("Analyze NQ futures", CognitiveDomain.TRADING),
        ("Analyze MNQ futures", CognitiveDomain.TRADING),
        ("Analyze stock fundamentals", CognitiveDomain.FINANCIAL),
        ("Compare crypto arbitrage", CognitiveDomain.CRYPTO),
        ("Review this marketing campaign", CognitiveDomain.MARKETING),
        ("Review business operations", CognitiveDomain.BUSINESS),
        ("Compare a career life decision", CognitiveDomain.LIFE_ADVICE),
        ("Retrieve Rosita family remedy knowledge", CognitiveDomain.ROSITA),
        ("Propose a computer action", CognitiveDomain.COMPUTER_ACTION),
    ),
)
def test_synthetic_scenarios_route_and_never_execute(text, expected):
    run = default_cognitive_core().process(_request(expected.value, text))
    assert run.intent.primary_domain is expected
    assert run.route.status in (DomainRouteStatus.SINGLE_DOMAIN, DomainRouteStatus.MULTI_DOMAIN)
    assert expected in run.route.domains
    assert run.action_performed is False
    assert run.external_model_used is False
    assert all(capability.execution_authority is False for capability in run.route.capabilities)
    if expected in {
        CognitiveDomain.TRADING, CognitiveDomain.FINANCIAL, CognitiveDomain.CRYPTO,
        CognitiveDomain.ROSITA, CognitiveDomain.COMPUTER_ACTION,
    }:
        assert all(capability.confirmation_required for capability in run.route.capabilities)
