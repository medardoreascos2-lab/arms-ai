"""R73B exact risk semantics tests for NQ and MNQ staging."""

from decimal import Decimal

import pytest

from backend.phase6.risk_semantics import (
    RiskValidationError,
    contract_dollar_exposure,
    size_contracts,
)


def test_same_stop_and_quantity_produce_ten_to_one_nq_mnq_exposure():
    nq = contract_dollar_exposure("NQ", Decimal("10.00"), 1)
    mnq = contract_dollar_exposure("MNQ", Decimal("10.00"), 1)

    assert nq == Decimal("200.0000")
    assert mnq == Decimal("20.0000")
    assert nq == mnq * Decimal("10")


def test_contract_sizing_is_instrument_aware_for_identical_inputs():
    nq = size_contracts("NQ", Decimal("10.00"), Decimal("200.00"), 20)
    mnq = size_contracts("MNQ", Decimal("10.00"), Decimal("200.00"), 20)

    assert nq.instrument == "NQ"
    assert mnq.instrument == "MNQ"
    assert nq.quantity == 1
    assert mnq.quantity == 10
    assert nq.per_contract_risk == Decimal("200.0000")
    assert mnq.per_contract_risk == Decimal("20.0000")
    assert nq.total_risk == mnq.total_risk == Decimal("200.0000")


def test_sequential_sizing_never_reuses_nq_or_mnq_point_value():
    first_mnq = size_contracts("MNQ", Decimal("5.00"), Decimal("200.00"), 50)
    nq = size_contracts("NQ", Decimal("5.00"), Decimal("200.00"), 50)
    second_mnq = size_contracts("MNQ", Decimal("5.00"), Decimal("200.00"), 50)

    assert first_mnq == second_mnq
    assert first_mnq.quantity == 20
    assert nq.quantity == 2
    assert first_mnq.point_value == Decimal("2.00")
    assert nq.point_value == Decimal("20.00")


def test_sizing_uses_only_decimal_and_never_authorizes_execution():
    result = size_contracts("NQ", Decimal("3.25"), Decimal("170.00"), 10)

    assert result.quantity == 2
    assert result.per_contract_risk == Decimal("65.0000")
    assert result.total_risk == Decimal("130.0000")
    assert result.unallocated_risk == Decimal("40.0000")
    assert result.accepted is True
    assert result.execution_authorized is False
    for value in (
        result.stop_points,
        result.point_value,
        result.per_contract_risk,
        result.risk_budget,
        result.total_risk,
        result.unallocated_risk,
    ):
        assert isinstance(value, Decimal)


def test_insufficient_budget_returns_zero_and_is_rejected():
    result = size_contracts("NQ", Decimal("10.00"), Decimal("199.99"), 10)

    assert result.accepted is False
    assert result.quantity == 0
    assert result.total_risk == Decimal("0.00")
    assert result.reason == "RISK_BUDGET_BELOW_ONE_CONTRACT"
    assert result.execution_authorized is False


@pytest.mark.parametrize("value", [10.0, "10.00", 10])
def test_non_decimal_risk_inputs_fail_closed(value):
    with pytest.raises(RiskValidationError, match="must be Decimal"):
        size_contracts("NQ", value, Decimal("200"), 10)
    with pytest.raises(RiskValidationError, match="must be Decimal"):
        size_contracts("NQ", Decimal("10"), value, 10)


def test_off_tick_stop_invalid_quantity_and_unknown_instrument_fail_closed():
    with pytest.raises(RiskValidationError, match="tick size"):
        contract_dollar_exposure("NQ", Decimal("1.10"), 1)
    with pytest.raises(RiskValidationError, match="positive integer"):
        contract_dollar_exposure("NQ", Decimal("1.00"), True)
    with pytest.raises(ValueError, match="unsupported"):
        contract_dollar_exposure("ES", Decimal("1.00"), 1)


def test_maximum_contract_limit_caps_both_instruments_independently():
    nq = size_contracts("NQ", Decimal("1.00"), Decimal("1000"), 3)
    mnq = size_contracts("MNQ", Decimal("1.00"), Decimal("1000"), 7)

    assert nq.quantity == 3
    assert mnq.quantity == 7
    assert nq.total_risk == Decimal("60.0000")
    assert mnq.total_risk == Decimal("14.0000")
