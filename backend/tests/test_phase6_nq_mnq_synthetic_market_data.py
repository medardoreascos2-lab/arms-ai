"""R73D synthetic NQ/MNQ staging dataset tests."""

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.phase6.synthetic_market_data import (
    SyntheticFixtureError,
    SyntheticScenario,
    build_synthetic_fixture_catalog,
)


NOW = datetime(2031, 3, 3, 15, 0, tzinfo=timezone.utc)


def test_catalog_has_every_required_scenario_for_nq_and_mnq():
    catalog = build_synthetic_fixture_catalog(NOW)

    assert set(catalog) == {"NQ", "MNQ"}
    for instrument in ("NQ", "MNQ"):
        assert set(catalog[instrument]) == set(SyntheticScenario)
        assert len(catalog[instrument]) == 7


def test_every_fixture_is_synthetic_scoped_and_has_no_execution_authority():
    catalog = build_synthetic_fixture_catalog(NOW)

    for instrument, fixtures in catalog.items():
        for fixture in fixtures.values():
            assert fixture.instrument == instrument
            assert fixture.contract_id == f"{instrument}-2031-03"
            assert fixture.dataset_id.startswith(f"synthetic-{instrument.lower()}-")
            assert fixture.provenance == "SYNTHETIC_PHASE6_FIXTURE"
            assert fixture.synthetic is True
            assert fixture.historical_performance_claimed is False
            assert fixture.execution_authorized is False


def test_price_data_is_decimal_tick_aligned_and_instrument_catalogs_are_distinct():
    catalog = build_synthetic_fixture_catalog(NOW)

    nq_ids = {fixture.dataset_id for fixture in catalog["NQ"].values()}
    mnq_ids = {fixture.dataset_id for fixture in catalog["MNQ"].values()}
    assert nq_ids.isdisjoint(mnq_ids)
    for fixtures in catalog.values():
        for fixture in fixtures.values():
            for bar in fixture.bars:
                assert all(
                    isinstance(value, Decimal) and value % Decimal("0.25") == 0
                    for value in (bar.open, bar.high, bar.low, bar.close)
                )


@pytest.mark.parametrize("instrument", ["NQ", "MNQ"])
def test_volatility_gap_and_spread_stress_have_distinct_synthetic_shape(instrument):
    fixtures = build_synthetic_fixture_catalog(NOW)[instrument]
    normal = fixtures[SyntheticScenario.NORMAL_VOLATILITY]
    high = fixtures[SyntheticScenario.HIGH_VOLATILITY]
    low = fixtures[SyntheticScenario.LOW_VOLATILITY]
    gap = fixtures[SyntheticScenario.GAP]
    stress = fixtures[SyntheticScenario.SPREAD_STRESS]

    normal_range = max(bar.high - bar.low for bar in normal.bars)
    high_range = max(bar.high - bar.low for bar in high.bars)
    low_range = max(bar.high - bar.low for bar in low.bars)
    assert high_range > normal_range > low_range
    assert gap.bars[1].open - gap.bars[0].close == Decimal("10.00")
    assert stress.spread_points == Decimal("5.00")
    assert normal.spread_points == Decimal("0.25")


@pytest.mark.parametrize("instrument", ["NQ", "MNQ"])
def test_stale_and_invalid_l1_fixtures_are_explicit(instrument):
    fixtures = build_synthetic_fixture_catalog(NOW)[instrument]
    stale = fixtures[SyntheticScenario.STALE_QUOTE]
    invalid = fixtures[SyntheticScenario.L1_INVALIDITY]

    assert stale.quote_age_seconds == Decimal("120.0")
    assert invalid.bid is None
    assert invalid.ask is not None
    assert invalid.spread_points is None


def test_fixture_guards_reject_real_history_or_execution_claims():
    fixture = build_synthetic_fixture_catalog(NOW)["NQ"][SyntheticScenario.NORMAL_VOLATILITY]

    with pytest.raises(SyntheticFixtureError, match="historical performance"):
        replace(fixture, historical_performance_claimed=True)
    with pytest.raises(SyntheticFixtureError, match="authorize execution"):
        replace(fixture, execution_authorized=True)
    with pytest.raises(SyntheticFixtureError, match="explicitly synthetic"):
        replace(fixture, synthetic=False)


def test_fixture_guards_reject_cross_instrument_and_naive_timestamp_inputs():
    fixture = build_synthetic_fixture_catalog(NOW)["MNQ"][SyntheticScenario.NORMAL_VOLATILITY]

    with pytest.raises(SyntheticFixtureError, match="contract identity"):
        replace(fixture, contract_id="NQ-2031-03")
    with pytest.raises(SyntheticFixtureError, match="timezone aware"):
        build_synthetic_fixture_catalog(datetime(2031, 3, 3, 15, 0))
