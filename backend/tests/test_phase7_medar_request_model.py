"""R80A MEDAR cognitive request model tests."""

import pytest

from backend.medar.request import (
    CognitiveDomain,
    CognitiveRequest,
    RiskClass,
    TimeSensitivity,
    normalize_user_input,
)


def _request(**overrides):
    values = {
        "request_id": "req-001",
        "conversation_id": "conv-001",
        "user_intent": "analyze NQ risk",
        "raw_input": "  Analyze   NQ risk  ",
        "normalized_input": "Analyze NQ risk",
        "domain": CognitiveDomain.TRADING,
        "risk_class": RiskClass.HIGH,
        "required_capabilities": ("financial_routing", "risk_analysis"),
        "time_sensitivity": TimeSensitivity.CURRENT,
        "requires_tools": True,
        "requires_human_confirmation": True,
    }
    values.update(overrides)
    return CognitiveRequest(**values)


def test_request_preserves_raw_input_and_canonical_metadata():
    request = _request()

    assert request.raw_input == "  Analyze   NQ risk  "
    assert request.normalized_input == "Analyze NQ risk"
    assert request.domain is CognitiveDomain.TRADING
    assert request.risk_class is RiskClass.HIGH
    assert request.required_capabilities == ("financial_routing", "risk_analysis")
    assert request.requires_tools is True
    assert request.requires_human_confirmation is True


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"request_id": ""}, ValueError),
        ({"normalized_input": "different"}, ValueError),
        ({"required_capabilities": ("risk", "risk")}, ValueError),
        ({"requires_web": 1}, TypeError),
    ],
)
def test_invalid_request_metadata_fails_closed(overrides, error):
    with pytest.raises(error):
        _request(**overrides)


def test_normalizer_rejects_blank_input():
    with pytest.raises(ValueError):
        normalize_user_input(" \n\t ")
