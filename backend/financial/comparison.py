"""Like-for-like company metric comparison with explicit missingness."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from backend.financial.fundamentals import CompanyFundamentals


class ComparisonStatus(str, Enum):
    COMPARABLE = "COMPARABLE"
    INCOMPLETE_DATA = "INCOMPLETE_DATA"


@dataclass(frozen=True)
class CompanyComparison:
    left_asset_id: str
    right_asset_id: str
    metric: str
    fiscal_period: str
    currency: str
    unit: str | None
    left_value: Decimal | None
    right_value: Decimal | None
    left_source: str | None
    right_source: str | None
    status: ComparisonStatus

    @property
    def difference(self) -> Decimal | None:
        if self.status is ComparisonStatus.INCOMPLETE_DATA:
            return None
        return self.left_value - self.right_value


def compare_companies(
    left: CompanyFundamentals, right: CompanyFundamentals, metric: str,
) -> CompanyComparison:
    if left.asset_id == right.asset_id:
        raise ValueError("comparison requires distinct companies")
    if left.fiscal_period != right.fiscal_period:
        raise ValueError("comparison requires the same fiscal period")
    if left.currency != right.currency:
        raise ValueError("comparison requires the same currency or explicit normalization")
    a, b = left.get(metric), right.get(metric)
    if a is None or b is None:
        return CompanyComparison(
            left.asset_id, right.asset_id, metric, left.fiscal_period, left.currency,
            None, a.value if a else None, b.value if b else None,
            a.source if a else None, b.source if b else None, ComparisonStatus.INCOMPLETE_DATA,
        )
    if a.unit != b.unit:
        raise ValueError("comparison requires the same unit or explicit normalization")
    return CompanyComparison(
        left.asset_id, right.asset_id, metric, left.fiscal_period, left.currency,
        a.unit, a.value, b.value, a.source, b.source, ComparisonStatus.COMPARABLE,
    )
