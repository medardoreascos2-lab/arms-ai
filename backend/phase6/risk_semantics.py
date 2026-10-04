"""Exact instrument-aware staging risk calculations for NQ and MNQ."""

from dataclasses import dataclass
from decimal import Decimal

from backend.phase6.instrument_registry import get_instrument


class RiskValidationError(ValueError):
    """Raised before sizing when required exact risk input is invalid."""


@dataclass(frozen=True)
class RiskSizingResult:
    instrument: str
    stop_points: Decimal
    point_value: Decimal
    per_contract_risk: Decimal
    risk_budget: Decimal
    maximum_contracts: int
    quantity: int
    total_risk: Decimal
    unallocated_risk: Decimal
    accepted: bool
    reason: str
    execution_authorized: bool = False


def _positive_decimal(value: Decimal, name: str) -> Decimal:
    if not isinstance(value, Decimal):
        raise RiskValidationError(f"{name} must be Decimal")
    if not value.is_finite() or value <= Decimal("0"):
        raise RiskValidationError(f"{name} must be finite and positive")
    return value


def _positive_quantity(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RiskValidationError(f"{name} must be a positive integer")
    return value


def _validated_stop(root_symbol: str, stop_points: Decimal) -> tuple[Decimal, Decimal]:
    instrument = get_instrument(root_symbol)
    stop = _positive_decimal(stop_points, "stop_points")
    ticks = stop / instrument.tick_size
    if ticks != ticks.to_integral_value():
        raise RiskValidationError("stop_points must align to the instrument tick size")
    return stop, instrument.point_value


def contract_dollar_exposure(
    root_symbol: str,
    stop_points: Decimal,
    quantity: int,
) -> Decimal:
    """Return exact stop exposure for an explicitly named instrument."""

    stop, point_value = _validated_stop(root_symbol, stop_points)
    contracts = _positive_quantity(quantity, "quantity")
    return stop * point_value * Decimal(contracts)


def size_contracts(
    root_symbol: str,
    stop_points: Decimal,
    risk_budget: Decimal,
    maximum_contracts: int,
) -> RiskSizingResult:
    """Size contracts with exact instrument semantics and fail closed at zero."""

    instrument = get_instrument(root_symbol)
    stop, point_value = _validated_stop(root_symbol, stop_points)
    budget = _positive_decimal(risk_budget, "risk_budget")
    maximum = _positive_quantity(maximum_contracts, "maximum_contracts")
    per_contract = stop * point_value
    affordable = int(budget // per_contract)
    quantity = min(affordable, maximum)
    total_risk = per_contract * Decimal(quantity)

    if quantity == 0:
        return RiskSizingResult(
            instrument=instrument.root_symbol,
            stop_points=stop,
            point_value=point_value,
            per_contract_risk=per_contract,
            risk_budget=budget,
            maximum_contracts=maximum,
            quantity=0,
            total_risk=Decimal("0.00"),
            unallocated_risk=budget,
            accepted=False,
            reason="RISK_BUDGET_BELOW_ONE_CONTRACT",
        )

    return RiskSizingResult(
        instrument=instrument.root_symbol,
        stop_points=stop,
        point_value=point_value,
        per_contract_risk=per_contract,
        risk_budget=budget,
        maximum_contracts=maximum,
        quantity=quantity,
        total_risk=total_risk,
        unallocated_risk=budget - total_risk,
        accepted=True,
        reason="SIZED_WITH_EXACT_INSTRUMENT_SEMANTICS",
    )
