"""Read-only multi-account prop-firm portfolio analytics tests."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from backend.prop_firms import (
    AccountSnapshot,
    AccountStage,
    AnalyticsAvailability,
    ExposurePosition,
    PayoutRequest,
    PropFirmAccountSnapshot,
    analyze_prop_firm_portfolio,
    canonical_profile_registry,
)


NOW = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)


def state(size: str, *, daily_pnl: str, high: str, balance: str, **changes):
    profit = D(balance) - D(size)
    values = dict(
        as_of=NOW,
        stage=AccountStage.EVALUATION,
        starting_balance=D(size),
        current_balance=D(balance),
        current_equity=D(balance),
        realized_pnl=profit,
        unrealized_pnl=D("0"),
        daily_pnl=D(daily_pnl),
        highest_end_of_day_balance=D(high),
        contracts_open=0,
        working_orders=0,
        contracts_traded=0,
        trading_days=2,
        best_day_profit=max(D("1"), profit),
        total_profit=profit,
        withdrawals=D("0"),
        prior_account_failed=False,
        session_id="session-1",
        daily_pnl_session_id="session-1",
        prior_session_blocked=False,
        trading_day_ends_at=NOW + timedelta(hours=2),
        exposures=(),
    )
    values.update(changes)
    return AccountSnapshot(**values)


def identified(account_id: str, size: str, account_state: AccountSnapshot):
    return PropFirmAccountSnapshot(
        account_id=account_id,
        firm_id="topstep",
        program_id="trading_combine",
        profile_version="2026-10-03/dll",
        stage=AccountStage.EVALUATION,
        account_size=D(size),
        captured_at=NOW,
        data_source=f"runtime://paper/{account_id}",
        simulated=True,
        state=account_state,
    )


def portfolio_snapshots():
    first = identified(
        "topstep-50",
        "50000",
        state(
            "50000",
            daily_pnl="-250",
            high="52500",
            balance="51500",
            contracts_open=11,
            contracts_traded=11,
            exposures=(ExposurePosition("NQ", 1), ExposurePosition("MNQ", 10)),
        ),
    )
    second = identified(
        "topstep-100",
        "100000",
        state(
            "100000",
            daily_pnl="-1000",
            high="103000",
            balance="101000",
            contracts_open=2,
            contracts_traded=2,
            exposures=(ExposurePosition("ES", 2),),
        ),
    )
    return first, second


def test_analytics_aggregate_money_utilization_exposure_and_distributions():
    snapshots = portfolio_snapshots()
    analytics = analyze_prop_firm_portfolio(
        canonical_profile_registry(),
        snapshots,
        payout_requests={
            item.account_id: PayoutRequest(D("500")) for item in snapshots
        },
    )

    assert analytics.balances.total == D("152500")
    assert analytics.balances.known_total == D("152500")
    assert analytics.balances.complete
    assert analytics.equities.total == D("152500")
    assert analytics.realized_pnl.total == D("2500")
    assert analytics.unrealized_pnl.total == D("0")

    drawdowns = {
        item.account_id: item for item in analytics.drawdown_utilization.accounts
    }
    assert drawdowns["topstep-50"].fraction == D("0.25")
    assert drawdowns["topstep-100"].fraction == D("2") / D("3")
    assert analytics.drawdown_utilization.maximum_fraction == D("2") / D("3")

    daily = {
        item.account_id: item for item in analytics.daily_limit_utilization.accounts
    }
    assert daily["topstep-50"].limit == D("1000")
    assert daily["topstep-50"].fraction == D("0.25")
    assert daily["topstep-100"].limit == D("2000")
    assert daily["topstep-100"].fraction == D("0.5")
    assert analytics.daily_limit_utilization.average_fraction == D("0.375")

    assert analytics.exposure.open_contracts.total == D("13")
    assert analytics.exposure.working_orders.total == D("0")
    assert analytics.exposure.instrument_quantities == (
        ("ES", 2), ("MNQ", 10), ("NQ", 1),
    )
    assert analytics.exposure.rule_status_counts == (("PASS", 2),)
    assert analytics.payout_readiness.ineligible_accounts == 2
    assert analytics.firm_distribution == (("topstep", 2),)
    assert analytics.stage_distribution == (("EVALUATION", 2),)
    assert analytics.accounts.total_accounts == 2
    assert analytics.accounts.simulated_snapshot_accounts == 2
    assert analytics.accounts.non_simulated_snapshot_accounts == 0
    assert not analytics.execution_authorized
    assert not analytics.diagnostics.execution_authorized


def test_missing_values_are_never_silently_substituted_into_complete_totals():
    healthy, second = portfolio_snapshots()
    missing_state = replace(
        second.state,
        current_balance=None,
        current_equity=None,
        realized_pnl=None,
        unrealized_pnl=None,
        daily_pnl=None,
        contracts_open=None,
        working_orders=None,
        exposures=None,
    )
    missing = replace(second, state=missing_state)
    analytics = analyze_prop_firm_portfolio(
        canonical_profile_registry(), (healthy, missing),
    )

    assert analytics.balances.total is None
    assert analytics.balances.known_total == healthy.balance
    assert analytics.balances.observed_accounts == 1
    assert analytics.balances.missing_account_ids == ("topstep-100",)
    assert not analytics.equities.complete
    assert analytics.realized_pnl.total is None
    assert analytics.unrealized_pnl.total is None
    assert analytics.exposure.open_contracts.total is None
    assert analytics.exposure.missing_exposure_account_ids == ("topstep-100",)
    assert analytics.daily_limit_utilization.incomplete_accounts == 1
    assert analytics.accounts.blocked_accounts == 1
    assert not analytics.execution_authorized


def test_unknown_profile_is_isolated_and_raw_snapshot_aggregates_remain_traceable():
    healthy, _ = portfolio_snapshots()
    unknown = replace(
        healthy,
        account_id="unknown-1",
        firm_id="unknown",
        program_id="missing",
        profile_version="v1",
        data_source="runtime://paper/unknown-1",
    )
    analytics = analyze_prop_firm_portfolio(
        canonical_profile_registry(), (unknown, healthy),
    )
    records = {
        item.account_id: item for item in analytics.drawdown_utilization.accounts
    }

    assert analytics.balances.total == healthy.balance * 2
    assert records["unknown-1"].availability == AnalyticsAvailability.INCOMPLETE
    assert records["topstep-50"].availability == AnalyticsAvailability.AVAILABLE
    assert analytics.accounts.blocked_accounts == 1
    assert analytics.accounts.source_status_counts == (
        ("CURRENT_VERIFIED", 1), ("UNRESOLVED", 1),
    )
    assert analytics.firm_distribution == (("topstep", 1), ("unknown", 1))


def test_empty_portfolio_has_zero_totals_and_no_invented_utilization():
    analytics = analyze_prop_firm_portfolio(canonical_profile_registry(), ())
    assert analytics.balances.total == D("0")
    assert analytics.balances.known_total == D("0")
    assert analytics.balances.complete
    assert analytics.drawdown_utilization.average_fraction is None
    assert analytics.daily_limit_utilization.maximum_fraction is None
    assert analytics.exposure.instrument_quantities == ()
    assert analytics.accounts.total_accounts == 0
    assert analytics.firm_distribution == ()
    assert analytics.stage_distribution == ()


def test_analysis_is_immutable_and_has_no_snapshot_or_execution_side_effect():
    snapshots = portfolio_snapshots()
    hashes = tuple(item.content_hash for item in snapshots)
    analytics = analyze_prop_firm_portfolio(
        canonical_profile_registry(), snapshots,
    )
    assert tuple(item.content_hash for item in snapshots) == hashes
    assert all(not item.execution_authorized for item in analytics.diagnostics.accounts)
    with pytest.raises(FrozenInstanceError):
        analytics.accounts.total_accounts = 99


def test_duplicate_accounts_and_invalid_input_still_fail_closed():
    snapshot = portfolio_snapshots()[0]
    with pytest.raises(ValueError, match="unique"):
        analyze_prop_firm_portfolio(
            canonical_profile_registry(), (snapshot, snapshot),
        )
    with pytest.raises(ValueError, match="immutable tuple"):
        analyze_prop_firm_portfolio(canonical_profile_registry(), [snapshot])
