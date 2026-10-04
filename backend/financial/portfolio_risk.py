"""Portfolio risk calculations from supplied, validated evidence only."""

from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

from backend.financial.portfolio import PortfolioSnapshot


def _valid(value: Decimal, *, minimum: Decimal | None = None, maximum: Decimal | None = None) -> bool:
    return (
        isinstance(value, Decimal) and value.is_finite()
        and (minimum is None or value >= minimum)
        and (maximum is None or value <= maximum)
    )


@dataclass(frozen=True)
class PortfolioRiskEvidence:
    volatility: Mapping[str, Decimal] = field(default_factory=dict)
    beta: Mapping[str, Decimal] = field(default_factory=dict)
    correlation: Mapping[tuple[str, str], Decimal] = field(default_factory=dict)
    average_daily_volume: Mapping[str, Decimal] = field(default_factory=dict)
    equity_path: tuple[Decimal, ...] = ()

    def __post_init__(self) -> None:
        if any(not _valid(v, minimum=Decimal(0)) for v in self.volatility.values()):
            raise ValueError("volatility must be nonnegative and finite")
        if any(not _valid(v) for v in self.beta.values()):
            raise ValueError("beta must be finite")
        if any(not _valid(v, minimum=Decimal(-1), maximum=Decimal(1)) for v in self.correlation.values()):
            raise ValueError("correlation must be between -1 and 1")
        if any(not _valid(v, minimum=Decimal(0)) or v == 0 for v in self.average_daily_volume.values()):
            raise ValueError("average daily volume must be positive")
        if any(not _valid(v, minimum=Decimal(0)) or v == 0 for v in self.equity_path):
            raise ValueError("equity path must contain positive finite values")
        for name in ("volatility", "beta", "correlation", "average_daily_volume"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))
        object.__setattr__(self, "equity_path", tuple(self.equity_path))


@dataclass(frozen=True)
class PortfolioRiskReport:
    concentration: Decimal | None
    sector_exposure: Mapping[str, Decimal] | None
    asset_class_exposure: Mapping[str, Decimal] | None
    max_pair_correlation: Decimal | None
    volatility: Decimal | None
    max_drawdown: Decimal | None
    beta: Decimal | None
    liquidity_days: Decimal | None
    single_name_risk: Decimal | None


def analyze_portfolio_risk(
    portfolio: PortfolioSnapshot, evidence: PortfolioRiskEvidence,
) -> PortfolioRiskReport:
    weights = portfolio.allocation()
    if weights is None:
        return PortfolioRiskReport(None, None, None, None, None, None, None, None, None)
    positions = portfolio.positions
    concentration = max(weights.values(), default=Decimal(0))
    sector = None
    if all(p.sector for p in positions):
        sector_values: dict[str, Decimal] = {}
        for p in positions:
            sector_values[p.sector] = sector_values.get(p.sector, Decimal(0)) + weights[p.asset_id]
        sector = MappingProxyType(sector_values)
    class_values: dict[str, Decimal] = {}
    for p in positions:
        key = p.asset_type.value
        class_values[key] = class_values.get(key, Decimal(0)) + weights[p.asset_id]
    pair_values = []
    complete_correlation = True
    for index, a in enumerate(positions):
        for b in positions[index + 1:]:
            key = (a.asset_id, b.asset_id)
            reverse = (b.asset_id, a.asset_id)
            value = evidence.correlation.get(key, evidence.correlation.get(reverse))
            if value is None:
                complete_correlation = False
            else:
                pair_values.append(value)
    max_pair_correlation = max(pair_values) if complete_correlation and pair_values else None
    volatility = None
    if all(p.asset_id in evidence.volatility for p in positions) and complete_correlation:
        variance = sum(
            (weights[p.asset_id] * evidence.volatility[p.asset_id]) ** 2
            for p in positions
        )
        for index, a in enumerate(positions):
            for b in positions[index + 1:]:
                corr = evidence.correlation.get((a.asset_id, b.asset_id),
                                                evidence.correlation.get((b.asset_id, a.asset_id)))
                variance += 2 * weights[a.asset_id] * weights[b.asset_id] * evidence.volatility[a.asset_id] * evidence.volatility[b.asset_id] * corr
        if variance >= 0:
            volatility = variance.sqrt()
    drawdown = None
    if len(evidence.equity_path) >= 2:
        peak = evidence.equity_path[0]
        drawdown = Decimal(0)
        for value in evidence.equity_path:
            peak = max(peak, value)
            drawdown = max(drawdown, (peak - value) / peak)
    beta = None
    if all(p.asset_id in evidence.beta for p in positions):
        beta = sum((weights[p.asset_id] * evidence.beta[p.asset_id] for p in positions), Decimal(0))
    liquidity = None
    if all(p.asset_id in evidence.average_daily_volume for p in positions):
        liquidity = max(
            (p.quantity / evidence.average_daily_volume[p.asset_id] for p in positions),
            default=Decimal(0),
        )
    return PortfolioRiskReport(
        concentration, sector, MappingProxyType(class_values), max_pair_correlation,
        volatility, drawdown, beta, liquidity, concentration,
    )
