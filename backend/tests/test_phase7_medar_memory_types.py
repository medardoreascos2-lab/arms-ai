"""R86A MEDAR memory domain tests."""

import pytest

from backend.medar.memory_types import MemoryDomain, MemorySensitivity, is_durable_domain


def test_memory_domains_match_phase7_contract():
    assert tuple(item.value for item in MemoryDomain) == (
        "WORKING", "EPISODIC", "SEMANTIC", "PERSONAL", "TECHNICAL",
        "TRADING", "FINANCIAL", "BUSINESS", "ROSITA", "TOOL", "RESEARCH",
    )


def test_working_memory_is_explicitly_non_durable():
    assert is_durable_domain(MemoryDomain.WORKING) is False
    assert is_durable_domain(MemoryDomain.PERSONAL) is True


def test_memory_sensitivity_is_canonical_and_typed():
    assert MemorySensitivity.RESTRICTED.value == "RESTRICTED"
    with pytest.raises(TypeError):
        is_durable_domain("PERSONAL")
