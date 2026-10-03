"""Independent, read-only evaluation of heterogeneous prop-firm accounts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping

from .account_snapshot import PropFirmAccountSnapshot
from .models_v1 import PayoutRequest, SourceStatus
from .profile_registry import (
    ProfileRegistryError, ProfileSourceStatusError, PropFirmProfileRegistry,
)
from .rule_engine_v2 import (
    AccountEvaluationV2, RuleOutcome, RuleScope, RuleStatus,
    evaluate_account_v2, evaluate_payout_v2,
)


@dataclass(frozen=True)
class AccountDiagnosticEvaluation:
    account_id: str
    firm_id: str
    program_id: str
    profile_version: str
    snapshot_hash: str
    source_status: SourceStatus | None
    account_valid: bool
    account_failed: bool
    trading_allowed_now: bool
    objective_status: str
    payout_status: str
    payout_evaluated: bool
    drawdown_state: RuleOutcome
    daily_loss_state: RuleOutcome
    exposure_state: RuleOutcome
    consistency_state: RuleOutcome
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    failure_reasons: tuple[str, ...]
    metrics: tuple[tuple[str, Decimal | int | str | bool | None], ...]
    profile_identity: str | None
    execution_authorized: bool = field(default=False, init=False)


@dataclass(frozen=True)
class MultiAccountDiagnosticSummary:
    accounts: tuple[AccountDiagnosticEvaluation, ...]
    total_accounts: int
    valid_accounts: int
    failed_accounts: int
    trading_allowed_accounts: int
    objective_met_accounts: int
    payout_eligible_accounts: int
    blocked_accounts: int
    source_status_counts: tuple[tuple[str, int], ...]
    execution_authorized: bool = field(default=False, init=False)


def _unavailable(rule_id: str, scope: RuleScope, reason: str) -> RuleOutcome:
    return RuleOutcome(rule_id, scope, RuleStatus.INCOMPLETE_DATA, reason)


def _outcome(
    evaluation: AccountEvaluationV2,
    rule_id: str,
    scope: RuleScope,
    *,
    alternatives: tuple[str, ...] = (),
) -> RuleOutcome:
    accepted = (rule_id,) + alternatives
    return next(
        (item for item in reversed(evaluation.outcomes) if item.rule_id in accepted),
        RuleOutcome(rule_id, scope, RuleStatus.NOT_APPLICABLE, "RULE_NOT_APPLICABLE"),
    )


def _blocked(
    snapshot: PropFirmAccountSnapshot,
    reason: str,
    source_status: SourceStatus | None,
    payout_evaluated: bool,
) -> AccountDiagnosticEvaluation:
    state_reason = "PROFILE_RESOLUTION_BLOCKED"
    return AccountDiagnosticEvaluation(
        account_id=snapshot.account_id,
        firm_id=snapshot.firm_id,
        program_id=snapshot.program_id,
        profile_version=snapshot.profile_version,
        snapshot_hash=snapshot.content_hash,
        source_status=source_status,
        account_valid=False,
        account_failed=False,
        trading_allowed_now=False,
        objective_status="BLOCKED",
        payout_status="BLOCKED" if payout_evaluated else "NOT_EVALUATED",
        payout_evaluated=payout_evaluated,
        drawdown_state=_unavailable("drawdown", RuleScope.ACCOUNT, state_reason),
        daily_loss_state=_unavailable("daily_loss", RuleScope.TRADING, state_reason),
        exposure_state=_unavailable("contracts", RuleScope.TRADING, state_reason),
        consistency_state=_unavailable("consistency", RuleScope.STAGE, state_reason),
        blocking_reasons=(reason,),
        warnings=(),
        failure_reasons=(),
        metrics=(),
        profile_identity=None,
    )


def _diagnostic(
    snapshot: PropFirmAccountSnapshot,
    evaluation: AccountEvaluationV2,
    payout_evaluated: bool,
) -> AccountDiagnosticEvaluation:
    payout_status = (
        "ELIGIBLE" if evaluation.payout_eligible else "INELIGIBLE"
    ) if payout_evaluated else "NOT_EVALUATED"
    return AccountDiagnosticEvaluation(
        account_id=snapshot.account_id,
        firm_id=snapshot.firm_id,
        program_id=snapshot.program_id,
        profile_version=snapshot.profile_version,
        snapshot_hash=snapshot.content_hash,
        source_status=evaluation.source_status,
        account_valid=evaluation.account_valid,
        account_failed=evaluation.account_failed,
        trading_allowed_now=evaluation.trading_allowed_now,
        objective_status="MET" if evaluation.stage_objective_met else "PENDING",
        payout_status=payout_status,
        payout_evaluated=payout_evaluated,
        drawdown_state=_outcome(evaluation, "drawdown", RuleScope.ACCOUNT),
        daily_loss_state=_outcome(evaluation, "daily_loss", RuleScope.TRADING),
        exposure_state=_outcome(evaluation, "contracts", RuleScope.TRADING),
        consistency_state=_outcome(
            evaluation, "consistency", RuleScope.STAGE,
            alternatives=("payout_cycle_consistency",),
        ),
        blocking_reasons=evaluation.blocking_reasons,
        warnings=evaluation.warnings,
        failure_reasons=evaluation.failure_reasons,
        metrics=evaluation.metrics,
        profile_identity=evaluation.profile_identity,
    )


def evaluate_accounts(
    registry: PropFirmProfileRegistry,
    snapshots: tuple[PropFirmAccountSnapshot, ...],
    *,
    payout_requests: Mapping[str, PayoutRequest] | None = None,
    require_current_sources: bool = True,
) -> MultiAccountDiagnosticSummary:
    """Evaluate accounts independently and return diagnostics with no authority."""
    if not isinstance(registry, PropFirmProfileRegistry):
        raise ValueError("registry must be a PropFirmProfileRegistry")
    if (not isinstance(snapshots, tuple)
            or any(not isinstance(item, PropFirmAccountSnapshot) for item in snapshots)):
        raise ValueError("snapshots must be an immutable tuple of account snapshots")
    if type(require_current_sources) is not bool:
        raise ValueError("require_current_sources must be a boolean")
    account_ids = [item.account_id for item in snapshots]
    if len(account_ids) != len(set(account_ids)):
        raise ValueError("account_id values must be unique")
    requests = dict(payout_requests or {})
    if any(not isinstance(key, str) or not isinstance(value, PayoutRequest)
           for key, value in requests.items()):
        raise ValueError("payout_requests must map account IDs to PayoutRequest values")
    unknown_requests = set(requests) - set(account_ids)
    if unknown_requests:
        raise ValueError("payout request references an unknown account")

    results = []
    for snapshot in snapshots:
        request = requests.get(snapshot.account_id)
        try:
            resolved = registry.resolve_profile(
                snapshot.firm_id,
                snapshot.program_id,
                snapshot.stage,
                snapshot.account_size,
                snapshot.captured_at,
                version=snapshot.profile_version,
                required_source_status=(
                    SourceStatus.CURRENT_VERIFIED if require_current_sources else None
                ),
            )
        except ProfileSourceStatusError as exc:
            results.append(_blocked(
                snapshot, f"PROFILE_SOURCE_STATUS_{exc.actual.value}",
                exc.actual, request is not None,
            ))
            continue
        except ProfileRegistryError as exc:
            results.append(_blocked(
                snapshot, f"PROFILE_RESOLUTION_{type(exc).__name__.upper()}",
                None, request is not None,
            ))
            continue

        evaluation = (
            evaluate_payout_v2(
                resolved.profile, snapshot.to_rule_snapshot(), request,
                require_current_sources=require_current_sources,
            )
            if request is not None
            else evaluate_account_v2(
                resolved.profile, snapshot.to_rule_snapshot(),
                require_current_sources=require_current_sources,
            )
        )
        results.append(_diagnostic(snapshot, evaluation, request is not None))

    accounts = tuple(results)
    statuses = Counter(
        item.source_status.value if item.source_status is not None else "UNRESOLVED"
        for item in accounts
    )
    return MultiAccountDiagnosticSummary(
        accounts=accounts,
        total_accounts=len(accounts),
        valid_accounts=sum(item.account_valid for item in accounts),
        failed_accounts=sum(item.account_failed for item in accounts),
        trading_allowed_accounts=sum(item.trading_allowed_now for item in accounts),
        objective_met_accounts=sum(item.objective_status == "MET" for item in accounts),
        payout_eligible_accounts=sum(item.payout_status == "ELIGIBLE" for item in accounts),
        blocked_accounts=sum(not item.account_valid for item in accounts),
        source_status_counts=tuple(sorted(statuses.items())),
    )
