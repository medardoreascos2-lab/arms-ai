"""Pure multi-account portfolio analytics over identified prop-firm snapshots."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Callable, Mapping

from .account_snapshot import PropFirmAccountSnapshot
from .models_v1 import PayoutRequest, PropFirmProfile, SourceStatus
from .multi_account_evaluator import (
    AccountDiagnosticEvaluation,
    MultiAccountDiagnosticSummary,
    evaluate_accounts,
)
from .profile_registry import ProfileRegistryError, PropFirmProfileRegistry
from .rule_engine_v2 import RuleStatus


class AnalyticsAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class NumericAggregate:
    """A complete total plus an explicitly labeled known-data subtotal."""

    total: Decimal | None
    known_total: Decimal
    observed_accounts: int
    missing_account_ids: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.missing_account_ids


@dataclass(frozen=True)
class AccountUtilization:
    account_id: str
    availability: AnalyticsAvailability
    limit: Decimal | None
    used: Decimal | None
    remaining: Decimal | None
    fraction: Decimal | None
    reason: str


@dataclass(frozen=True)
class UtilizationSummary:
    accounts: tuple[AccountUtilization, ...]
    available_accounts: int
    incomplete_accounts: int
    not_applicable_accounts: int
    average_fraction: Decimal | None
    maximum_fraction: Decimal | None


@dataclass(frozen=True)
class ExposureAnalytics:
    open_contracts: NumericAggregate
    working_orders: NumericAggregate
    instrument_quantities: tuple[tuple[str, int], ...]
    observed_exposure_accounts: int
    missing_exposure_account_ids: tuple[str, ...]
    rule_status_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class PayoutReadiness:
    eligible_accounts: int
    ineligible_accounts: int
    blocked_accounts: int
    not_evaluated_accounts: int


@dataclass(frozen=True)
class AccountDistribution:
    total_accounts: int
    valid_accounts: int
    failed_accounts: int
    trading_allowed_accounts: int
    blocked_accounts: int
    simulated_snapshot_accounts: int
    non_simulated_snapshot_accounts: int
    source_status_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class PropFirmPortfolioAnalytics:
    balances: NumericAggregate
    equities: NumericAggregate
    realized_pnl: NumericAggregate
    unrealized_pnl: NumericAggregate
    drawdown_utilization: UtilizationSummary
    daily_limit_utilization: UtilizationSummary
    exposure: ExposureAnalytics
    payout_readiness: PayoutReadiness
    accounts: AccountDistribution
    firm_distribution: tuple[tuple[str, int], ...]
    stage_distribution: tuple[tuple[str, int], ...]
    diagnostics: MultiAccountDiagnosticSummary
    execution_authorized: bool = field(default=False, init=False)


def _aggregate(
    snapshots: tuple[PropFirmAccountSnapshot, ...],
    getter: Callable[[PropFirmAccountSnapshot], Decimal | int | None],
) -> NumericAggregate:
    values: list[Decimal] = []
    missing = []
    for snapshot in snapshots:
        value = getter(snapshot)
        if value is None:
            missing.append(snapshot.account_id)
        else:
            values.append(value if isinstance(value, Decimal) else Decimal(value))
    known = sum(values, Decimal("0"))
    return NumericAggregate(
        total=known if not missing else None,
        known_total=known,
        observed_accounts=len(values),
        missing_account_ids=tuple(missing),
    )


def _utilization_summary(
    records: tuple[AccountUtilization, ...],
) -> UtilizationSummary:
    fractions = tuple(
        item.fraction for item in records
        if item.availability == AnalyticsAvailability.AVAILABLE
        and item.fraction is not None
    )
    return UtilizationSummary(
        accounts=records,
        available_accounts=len(fractions),
        incomplete_accounts=sum(
            item.availability == AnalyticsAvailability.INCOMPLETE for item in records
        ),
        not_applicable_accounts=sum(
            item.availability == AnalyticsAvailability.NOT_APPLICABLE
            for item in records
        ),
        average_fraction=(
            sum(fractions, Decimal("0")) / len(fractions) if fractions else None
        ),
        maximum_fraction=max(fractions) if fractions else None,
    )


def _resolved_profiles(
    registry: PropFirmProfileRegistry,
    snapshots: tuple[PropFirmAccountSnapshot, ...],
    require_current_sources: bool,
) -> dict[str, PropFirmProfile]:
    profiles = {}
    required = SourceStatus.CURRENT_VERIFIED if require_current_sources else None
    for snapshot in snapshots:
        try:
            profiles[snapshot.account_id] = registry.resolve_profile(
                snapshot.firm_id,
                snapshot.program_id,
                snapshot.stage,
                snapshot.account_size,
                snapshot.captured_at,
                version=snapshot.profile_version,
                required_source_status=required,
            ).profile
        except ProfileRegistryError:
            continue
    return profiles


def _drawdown_records(
    snapshots: tuple[PropFirmAccountSnapshot, ...],
    diagnostics: Mapping[str, AccountDiagnosticEvaluation],
    profiles: Mapping[str, PropFirmProfile],
) -> tuple[AccountUtilization, ...]:
    records = []
    for snapshot in snapshots:
        diagnostic = diagnostics[snapshot.account_id]
        profile = profiles.get(snapshot.account_id)
        outcome = diagnostic.drawdown_state
        if outcome.status == RuleStatus.NOT_APPLICABLE:
            records.append(AccountUtilization(
                snapshot.account_id, AnalyticsAvailability.NOT_APPLICABLE,
                None, None, None, None, outcome.reason,
            ))
            continue
        metrics = dict(diagnostic.metrics)
        limit = profile.drawdown.maximum_loss if profile is not None else None
        remaining = metrics.get("remaining_drawdown")
        if not isinstance(limit, Decimal) or not isinstance(remaining, Decimal):
            records.append(AccountUtilization(
                snapshot.account_id, AnalyticsAvailability.INCOMPLETE,
                limit if isinstance(limit, Decimal) else None,
                None, remaining if isinstance(remaining, Decimal) else None,
                None, outcome.reason,
            ))
            continue
        used = max(Decimal("0"), limit - remaining)
        records.append(AccountUtilization(
            snapshot.account_id, AnalyticsAvailability.AVAILABLE,
            limit, used, remaining, used / limit, outcome.reason,
        ))
    return tuple(records)


def _daily_records(
    snapshots: tuple[PropFirmAccountSnapshot, ...],
    diagnostics: Mapping[str, AccountDiagnosticEvaluation],
) -> tuple[AccountUtilization, ...]:
    records = []
    for snapshot in snapshots:
        outcome = diagnostics[snapshot.account_id].daily_loss_state
        if outcome.status == RuleStatus.NOT_APPLICABLE:
            records.append(AccountUtilization(
                snapshot.account_id, AnalyticsAvailability.NOT_APPLICABLE,
                None, None, None, None, outcome.reason,
            ))
            continue
        evidence = dict(outcome.evidence)
        used = evidence.get("used")
        remaining = evidence.get("remaining")
        if not isinstance(used, Decimal) or not isinstance(remaining, Decimal):
            records.append(AccountUtilization(
                snapshot.account_id, AnalyticsAvailability.INCOMPLETE,
                None, None, None, None, outcome.reason,
            ))
            continue
        limit = used + remaining
        if limit <= 0:
            records.append(AccountUtilization(
                snapshot.account_id, AnalyticsAvailability.INCOMPLETE,
                None, used, remaining, None, "INVALID_DAILY_LOSS_LIMIT",
            ))
            continue
        records.append(AccountUtilization(
            snapshot.account_id, AnalyticsAvailability.AVAILABLE,
            limit, used, remaining, used / limit, outcome.reason,
        ))
    return tuple(records)


def _exposure(
    snapshots: tuple[PropFirmAccountSnapshot, ...],
    diagnostics: Mapping[str, AccountDiagnosticEvaluation],
) -> ExposureAnalytics:
    quantities: Counter[str] = Counter()
    missing = []
    observed = 0
    for snapshot in snapshots:
        positions = snapshot.open_exposure
        if positions is None:
            missing.append(snapshot.account_id)
            continue
        observed += 1
        for position in positions:
            quantities[position.instrument] += position.quantity
    statuses = Counter(
        diagnostics[snapshot.account_id].exposure_state.status.value
        for snapshot in snapshots
    )
    return ExposureAnalytics(
        open_contracts=_aggregate(snapshots, lambda item: item.state.contracts_open),
        working_orders=_aggregate(snapshots, lambda item: item.state.working_orders),
        instrument_quantities=tuple(sorted(quantities.items())),
        observed_exposure_accounts=observed,
        missing_exposure_account_ids=tuple(missing),
        rule_status_counts=tuple(sorted(statuses.items())),
    )


def analyze_prop_firm_portfolio(
    registry: PropFirmProfileRegistry,
    snapshots: tuple[PropFirmAccountSnapshot, ...],
    *,
    payout_requests: Mapping[str, PayoutRequest] | None = None,
    require_current_sources: bool = True,
) -> PropFirmPortfolioAnalytics:
    """Aggregate immutable snapshots and diagnostics without granting authority."""
    diagnostics = evaluate_accounts(
        registry,
        snapshots,
        payout_requests=payout_requests,
        require_current_sources=require_current_sources,
    )
    by_id = {item.account_id: item for item in diagnostics.accounts}
    profiles = _resolved_profiles(registry, snapshots, require_current_sources)
    payout_counts = Counter(item.payout_status for item in diagnostics.accounts)
    firm_counts = Counter(item.firm_id for item in snapshots)
    stage_counts = Counter(item.stage.value for item in snapshots)
    return PropFirmPortfolioAnalytics(
        balances=_aggregate(snapshots, lambda item: item.balance),
        equities=_aggregate(snapshots, lambda item: item.equity),
        realized_pnl=_aggregate(snapshots, lambda item: item.realized_pnl),
        unrealized_pnl=_aggregate(snapshots, lambda item: item.unrealized_pnl),
        drawdown_utilization=_utilization_summary(
            _drawdown_records(snapshots, by_id, profiles)
        ),
        daily_limit_utilization=_utilization_summary(
            _daily_records(snapshots, by_id)
        ),
        exposure=_exposure(snapshots, by_id),
        payout_readiness=PayoutReadiness(
            eligible_accounts=payout_counts["ELIGIBLE"],
            ineligible_accounts=payout_counts["INELIGIBLE"],
            blocked_accounts=payout_counts["BLOCKED"],
            not_evaluated_accounts=payout_counts["NOT_EVALUATED"],
        ),
        accounts=AccountDistribution(
            total_accounts=diagnostics.total_accounts,
            valid_accounts=diagnostics.valid_accounts,
            failed_accounts=diagnostics.failed_accounts,
            trading_allowed_accounts=diagnostics.trading_allowed_accounts,
            blocked_accounts=diagnostics.blocked_accounts,
            simulated_snapshot_accounts=sum(item.simulated for item in snapshots),
            non_simulated_snapshot_accounts=sum(not item.simulated for item in snapshots),
            source_status_counts=diagnostics.source_status_counts,
        ),
        firm_distribution=tuple(sorted(firm_counts.items())),
        stage_distribution=tuple(sorted(stage_counts.items())),
        diagnostics=diagnostics,
    )
