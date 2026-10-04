"""Canonical NQ/MNQ staging definitions with exact decimal semantics."""

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping


class InstrumentRegistryError(ValueError):
    """Raised when an instrument or contract identity is invalid."""


@dataclass(frozen=True)
class TradingSession:
    name: str
    timezone: str
    weekly_open_day: str
    weekly_open_time: str
    weekly_close_day: str
    weekly_close_time: str
    daily_maintenance_start: str
    daily_maintenance_end: str
    intraday_halt_start: str
    intraday_halt_end: str


@dataclass(frozen=True)
class ContractResolutionPolicy:
    canonical_id_pattern: str
    exchange_symbol_pattern: str
    quarterly_months: tuple[int, ...]
    listed_contract_count: int
    expiration_rule: str
    resolver: str
    rollover_trigger: str
    current_contract_is_static: bool = False


@dataclass(frozen=True)
class InstrumentDefinition:
    root_symbol: str
    symbol_family: str
    exchange: str
    venue: str
    currency: str
    tick_size: Decimal
    point_value: Decimal
    contract_multiplier: Decimal
    session: TradingSession
    contract_resolution: ContractResolutionPolicy

    @property
    def tick_value(self) -> Decimal:
        return self.tick_size * self.point_value

    def canonical_contract_id(self, year: int, month: int) -> str:
        if year < 2000 or year > 9999:
            raise InstrumentRegistryError("contract year must use four digits")
        if month not in self.contract_resolution.quarterly_months:
            raise InstrumentRegistryError("contract month is outside the quarterly cycle")
        return self.contract_resolution.canonical_id_pattern.format(
            root=self.root_symbol,
            year=year,
            month=month,
        )


CME_EQUITY_INDEX_SESSION = TradingSession(
    name="CME_GLOBEX_US_EQUITY_INDEX",
    timezone="America/New_York",
    weekly_open_day="SUNDAY",
    weekly_open_time="18:00:00",
    weekly_close_day="FRIDAY",
    weekly_close_time="17:00:00",
    daily_maintenance_start="17:00:00",
    daily_maintenance_end="18:00:00",
    intraday_halt_start="16:15:00",
    intraday_halt_end="16:30:00",
)


CME_QUARTERLY_RESOLUTION = ContractResolutionPolicy(
    canonical_id_pattern="{root}-{year:04d}-{month:02d}",
    exchange_symbol_pattern="{root}{month_code}{year_digit}",
    quarterly_months=(3, 6, 9, 12),
    listed_contract_count=5,
    expiration_rule="third_friday_opening_index_settlement",
    resolver="eligible_contracts_then_liquidity_aware_roll_policy",
    rollover_trigger="approved_volume_crossover_or_configured_days_before_expiry",
)


_INSTRUMENTS = {
    "NQ": InstrumentDefinition(
        root_symbol="NQ",
        symbol_family="NASDAQ_100_EQUITY_INDEX_FUTURES",
        exchange="CME",
        venue="CME_GLOBEX",
        currency="USD",
        tick_size=Decimal("0.25"),
        point_value=Decimal("20.00"),
        contract_multiplier=Decimal("20.00"),
        session=CME_EQUITY_INDEX_SESSION,
        contract_resolution=CME_QUARTERLY_RESOLUTION,
    ),
    "MNQ": InstrumentDefinition(
        root_symbol="MNQ",
        symbol_family="NASDAQ_100_EQUITY_INDEX_FUTURES",
        exchange="CME",
        venue="CME_GLOBEX",
        currency="USD",
        tick_size=Decimal("0.25"),
        point_value=Decimal("2.00"),
        contract_multiplier=Decimal("2.00"),
        session=CME_EQUITY_INDEX_SESSION,
        contract_resolution=CME_QUARTERLY_RESOLUTION,
    ),
}

INSTRUMENTS: Mapping[str, InstrumentDefinition] = MappingProxyType(_INSTRUMENTS)


def get_instrument(root_symbol: str) -> InstrumentDefinition:
    """Return an exact canonical definition without aliasing NQ and MNQ."""

    if not isinstance(root_symbol, str):
        raise InstrumentRegistryError("root symbol must be text")
    normalized = root_symbol.strip().upper()
    try:
        return INSTRUMENTS[normalized]
    except KeyError as exc:
        raise InstrumentRegistryError(f"unsupported staging instrument: {normalized}") from exc
