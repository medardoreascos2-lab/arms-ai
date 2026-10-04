"""Deterministic synthetic NQ/MNQ fixtures for Phase 6 staging validation."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from backend.phase6.instrument_registry import get_instrument


class SyntheticFixtureError(ValueError):
    """Raised when a staging fixture is incomplete or misrepresents its origin."""


class SyntheticScenario(str, Enum):
    NORMAL_VOLATILITY = "NORMAL_VOLATILITY"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    GAP = "GAP"
    SPREAD_STRESS = "SPREAD_STRESS"
    STALE_QUOTE = "STALE_QUOTE"
    L1_INVALIDITY = "L1_INVALIDITY"


@dataclass(frozen=True)
class SyntheticBar:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True)
class SyntheticMarketFixture:
    dataset_id: str
    instrument: str
    contract_id: str
    scenario: SyntheticScenario
    bars: tuple[SyntheticBar, ...]
    reference_time: datetime
    quote_time: datetime
    bid: Decimal | None
    ask: Decimal | None
    provenance: str = "SYNTHETIC_PHASE6_FIXTURE"
    synthetic: bool = True
    historical_performance_claimed: bool = False
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        definition = get_instrument(self.instrument)
        if self.instrument != definition.root_symbol:
            raise SyntheticFixtureError("instrument must use the canonical root symbol")
        if not self.contract_id.startswith(f"{self.instrument}-"):
            raise SyntheticFixtureError("contract identity does not match instrument")
        if not self.dataset_id.startswith(f"synthetic-{self.instrument.lower()}-"):
            raise SyntheticFixtureError("dataset identity must declare instrument scope")
        if not isinstance(self.scenario, SyntheticScenario):
            raise SyntheticFixtureError("scenario must be a SyntheticScenario")
        if not self.bars:
            raise SyntheticFixtureError("synthetic fixture requires bars")
        if not self.synthetic or self.provenance != "SYNTHETIC_PHASE6_FIXTURE":
            raise SyntheticFixtureError("fixture provenance must remain explicitly synthetic")
        if self.historical_performance_claimed:
            raise SyntheticFixtureError("synthetic fixtures cannot claim historical performance")
        if self.execution_authorized:
            raise SyntheticFixtureError("synthetic fixtures cannot authorize execution")
        if self.reference_time.tzinfo is None or self.quote_time.tzinfo is None:
            raise SyntheticFixtureError("fixture timestamps must be timezone aware")
        for bar in self.bars:
            self._validate_bar(bar, definition.tick_size)

        if self.scenario == SyntheticScenario.L1_INVALIDITY:
            if self.bid is not None and self.ask is not None:
                raise SyntheticFixtureError("L1 invalidity must contain an incomplete quote")
        else:
            self._validate_quote(definition.tick_size)

    def _validate_bar(self, bar: SyntheticBar, tick_size: Decimal) -> None:
        if bar.timestamp.tzinfo is None:
            raise SyntheticFixtureError("bar timestamps must be timezone aware")
        if isinstance(bar.volume, bool) or not isinstance(bar.volume, int) or bar.volume < 0:
            raise SyntheticFixtureError("bar volume must be a nonnegative integer")
        prices = (bar.open, bar.high, bar.low, bar.close)
        if any(not isinstance(value, Decimal) or not value.is_finite() for value in prices):
            raise SyntheticFixtureError("bar prices must be finite Decimal values")
        if any(value / tick_size != (value / tick_size).to_integral_value() for value in prices):
            raise SyntheticFixtureError("bar prices must align to instrument tick size")
        if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
            raise SyntheticFixtureError("bar OHLC bounds are inconsistent")

    def _validate_quote(self, tick_size: Decimal) -> None:
        if not isinstance(self.bid, Decimal) or not isinstance(self.ask, Decimal):
            raise SyntheticFixtureError("complete L1 quote requires Decimal bid and ask")
        if not self.bid.is_finite() or not self.ask.is_finite() or self.bid <= 0:
            raise SyntheticFixtureError("L1 prices must be finite and positive")
        if self.ask < self.bid:
            raise SyntheticFixtureError("L1 quote cannot be crossed")
        if self.bid / tick_size != (self.bid / tick_size).to_integral_value():
            raise SyntheticFixtureError("L1 bid must align to instrument tick size")
        if self.ask / tick_size != (self.ask / tick_size).to_integral_value():
            raise SyntheticFixtureError("L1 ask must align to instrument tick size")

    @property
    def quote_age_seconds(self) -> Decimal:
        return Decimal(str((self.reference_time - self.quote_time).total_seconds()))

    @property
    def spread_points(self) -> Decimal | None:
        if self.bid is None or self.ask is None:
            return None
        return self.ask - self.bid


_BASE_PRICE = {"NQ": Decimal("20000.00"), "MNQ": Decimal("16000.00")}


def _bar(
    timestamp: datetime,
    base: Decimal,
    offsets: tuple[str, str, str, str],
    volume: int,
) -> SyntheticBar:
    values = tuple(base + Decimal(offset) for offset in offsets)
    return SyntheticBar(timestamp, values[0], values[1], values[2], values[3], volume)


def _bars_for(scenario: SyntheticScenario, start: datetime, base: Decimal) -> tuple[SyntheticBar, ...]:
    templates = {
        SyntheticScenario.NORMAL_VOLATILITY: (
            (("0", "2.00", "-1.00", "1.25"), 1100),
            (("1.25", "3.00", "0.50", "2.25"), 1250),
            (("2.25", "3.25", "0.75", "1.50"), 1180),
        ),
        SyntheticScenario.HIGH_VOLATILITY: (
            (("0", "12.00", "-8.00", "9.00"), 4800),
            (("9.00", "15.00", "-5.00", "-2.00"), 5300),
            (("-2.00", "10.00", "-14.00", "7.00"), 5100),
        ),
        SyntheticScenario.LOW_VOLATILITY: (
            (("0", "0.50", "-0.25", "0.25"), 280),
            (("0.25", "0.50", "0", "0.25"), 240),
            (("0.25", "0.50", "0", "0"), 260),
        ),
        SyntheticScenario.GAP: (
            (("0", "2.00", "-1.00", "1.00"), 900),
            (("11.00", "13.00", "10.00", "12.00"), 2100),
            (("12.00", "14.00", "11.00", "13.00"), 1700),
        ),
        SyntheticScenario.SPREAD_STRESS: (
            (("0", "1.00", "-1.00", "0.50"), 700),
            (("0.50", "1.50", "-0.50", "0.75"), 650),
            (("0.75", "1.75", "0", "1.00"), 720),
        ),
        SyntheticScenario.STALE_QUOTE: (
            (("0", "1.50", "-1.00", "0.75"), 620),
            (("0.75", "2.00", "0", "1.25"), 660),
            (("1.25", "2.25", "0.25", "1.50"), 680),
        ),
        SyntheticScenario.L1_INVALIDITY: (
            (("0", "1.00", "-0.75", "0.25"), 500),
            (("0.25", "1.25", "-0.50", "0.50"), 520),
            (("0.50", "1.50", "-0.25", "0.75"), 510),
        ),
    }
    return tuple(
        _bar(start + timedelta(minutes=index), base, offsets, volume)
        for index, (offsets, volume) in enumerate(templates[scenario])
    )


def build_synthetic_fixture_catalog(
    reference_time: datetime | None = None,
) -> Mapping[str, Mapping[SyntheticScenario, SyntheticMarketFixture]]:
    """Return complete, immutable, instrument-separated synthetic scenario fixtures."""

    now = reference_time or datetime(2031, 3, 3, 15, 0, tzinfo=timezone.utc)
    if now.tzinfo is None:
        raise SyntheticFixtureError("reference_time must be timezone aware")
    catalog: dict[str, Mapping[SyntheticScenario, SyntheticMarketFixture]] = {}
    for instrument, base in _BASE_PRICE.items():
        scenarios: dict[SyntheticScenario, SyntheticMarketFixture] = {}
        for scenario in SyntheticScenario:
            quote_time = now - timedelta(seconds=120) if scenario == SyntheticScenario.STALE_QUOTE else now
            bid: Decimal | None = base
            ask: Decimal | None = base + (
                Decimal("5.00") if scenario == SyntheticScenario.SPREAD_STRESS else Decimal("0.25")
            )
            if scenario == SyntheticScenario.L1_INVALIDITY:
                bid = None
            scenarios[scenario] = SyntheticMarketFixture(
                dataset_id=f"synthetic-{instrument.lower()}-{scenario.value.lower().replace('_', '-')}-v1",
                instrument=instrument,
                contract_id=f"{instrument}-2031-03",
                scenario=scenario,
                bars=_bars_for(scenario, now - timedelta(minutes=3), base),
                reference_time=now,
                quote_time=quote_time,
                bid=bid,
                ask=ask,
            )
        catalog[instrument] = MappingProxyType(scenarios)
    return MappingProxyType(catalog)
