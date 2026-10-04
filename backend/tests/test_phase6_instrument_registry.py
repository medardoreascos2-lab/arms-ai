"""R73A tests for canonical exact NQ/MNQ staging definitions."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from backend.phase6.instrument_registry import (
    INSTRUMENTS,
    InstrumentRegistryError,
    get_instrument,
)


def test_registry_contains_distinct_nq_and_mnq_exact_definitions():
    assert set(INSTRUMENTS) == {"NQ", "MNQ"}
    nq = get_instrument("nq")
    mnq = get_instrument(" MNQ ")

    assert nq is not mnq
    assert nq.root_symbol == "NQ"
    assert mnq.root_symbol == "MNQ"
    assert nq.tick_size == mnq.tick_size == Decimal("0.25")
    assert nq.point_value == nq.contract_multiplier == Decimal("20.00")
    assert mnq.point_value == mnq.contract_multiplier == Decimal("2.00")
    assert nq.tick_value == Decimal("5.0000")
    assert mnq.tick_value == Decimal("0.5000")
    assert nq.tick_value == mnq.tick_value * Decimal("10")


def test_registry_metadata_has_exchange_session_and_dynamic_roll_contract():
    for instrument in INSTRUMENTS.values():
        assert instrument.exchange == "CME"
        assert instrument.venue == "CME_GLOBEX"
        assert instrument.session.timezone == "America/New_York"
        assert instrument.session.weekly_open_day == "SUNDAY"
        assert instrument.session.weekly_close_day == "FRIDAY"
        assert instrument.contract_resolution.quarterly_months == (3, 6, 9, 12)
        assert instrument.contract_resolution.listed_contract_count == 5
        assert instrument.contract_resolution.current_contract_is_static is False
        assert "liquidity" in instrument.contract_resolution.resolver


def test_contract_identity_requires_explicit_four_digit_year_and_quarterly_month():
    nq = get_instrument("NQ")

    assert nq.canonical_contract_id(2031, 3) == "NQ-2031-03"
    assert nq.canonical_contract_id(2031, 12) == "NQ-2031-12"
    with pytest.raises(InstrumentRegistryError, match="four digits"):
        nq.canonical_contract_id(31, 3)
    with pytest.raises(InstrumentRegistryError, match="quarterly cycle"):
        nq.canonical_contract_id(2031, 4)


def test_registry_and_definitions_are_immutable():
    with pytest.raises(TypeError):
        INSTRUMENTS["NQ"] = get_instrument("NQ")
    with pytest.raises(FrozenInstanceError):
        get_instrument("NQ").point_value = Decimal("2")


def test_unknown_or_non_text_instrument_fails_closed():
    with pytest.raises(InstrumentRegistryError, match="unsupported"):
        get_instrument("ES")
    with pytest.raises(InstrumentRegistryError, match="must be text"):
        get_instrument(None)
