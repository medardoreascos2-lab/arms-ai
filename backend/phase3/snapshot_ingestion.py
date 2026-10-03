"""Pure validation and sequencing contract for Phase 3 account snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import re

from backend.prop_firms import PropFirmAccountSnapshot

from .state_contracts import (
    AccountIdentity,
    DecimalUnit,
    PropFirmProfileIdentity,
    SourceIdentity,
    TenantIdentity,
)


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")


def _aware(value: object, name: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")


class SnapshotSourceKind(str, Enum):
    BROKER_CONNECTOR = "BROKER_CONNECTOR"
    MANUAL_IMPORT = "MANUAL_IMPORT"
    PROP_FIRM_API = "PROP_FIRM_API"
    PAPER = "PAPER"
    FILE_IMPORT = "FILE_IMPORT"


class IngestionCode(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE_IDEMPOTENT = "DUPLICATE_IDEMPOTENT"
    DUPLICATE_CONFLICT = "DUPLICATE_CONFLICT"
    OUT_OF_ORDER_SEQUENCE = "OUT_OF_ORDER_SEQUENCE"
    OUT_OF_ORDER_TIMESTAMP = "OUT_OF_ORDER_TIMESTAMP"
    CURSOR_SCOPE_MISMATCH = "CURSOR_SCOPE_MISMATCH"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    PROFILE_MISMATCH = "PROFILE_MISMATCH"
    SOURCE_MISMATCH = "SOURCE_MISMATCH"
    INCOMPLETE_FINANCIAL_STATE = "INCOMPLETE_FINANCIAL_STATE"
    INCONSISTENT_FINANCIAL_STATE = "INCONSISTENT_FINANCIAL_STATE"
    STALE_SNAPSHOT = "STALE_SNAPSHOT"
    FUTURE_SNAPSHOT = "FUTURE_SNAPSHOT"
    INVALID_RECEIPT_TIME = "INVALID_RECEIPT_TIME"


@dataclass(frozen=True)
class SnapshotIngestionSource:
    identity: SourceIdentity
    kind: SnapshotSourceKind

    def __post_init__(self) -> None:
        if not isinstance(self.identity, SourceIdentity):
            raise ValueError("identity must be a SourceIdentity")
        if not isinstance(self.kind, SnapshotSourceKind):
            raise ValueError("kind must be a SnapshotSourceKind")
        if self.kind is SnapshotSourceKind.PAPER and not self.identity.simulated:
            raise ValueError("PAPER source must be simulated")


@dataclass(frozen=True)
class SnapshotFreshnessPolicy:
    maximum_age_seconds: int
    maximum_future_skew_seconds: int = 5

    def __post_init__(self) -> None:
        if type(self.maximum_age_seconds) is not int or self.maximum_age_seconds <= 0:
            raise ValueError("maximum_age_seconds must be a positive integer")
        if (
            type(self.maximum_future_skew_seconds) is not int
            or self.maximum_future_skew_seconds < 0
        ):
            raise ValueError("maximum_future_skew_seconds must be nonnegative")


@dataclass(frozen=True)
class SnapshotIngestionRequest:
    ingestion_id: str
    tenant: TenantIdentity
    account: AccountIdentity
    profile: PropFirmProfileIdentity
    source: SnapshotIngestionSource
    sequence: int
    received_at: datetime
    currency: str
    snapshot: PropFirmAccountSnapshot

    def __post_init__(self) -> None:
        if not isinstance(self.ingestion_id, str) or _ID.fullmatch(self.ingestion_id) is None:
            raise ValueError("ingestion_id must be a safe identifier")
        if not isinstance(self.tenant, TenantIdentity):
            raise ValueError("tenant must be a TenantIdentity")
        if not isinstance(self.account, AccountIdentity):
            raise ValueError("account must be an AccountIdentity")
        if self.account.tenant_id != self.tenant.tenant_id:
            raise ValueError("account tenant must match request tenant")
        if not isinstance(self.profile, PropFirmProfileIdentity):
            raise ValueError("profile must be a PropFirmProfileIdentity")
        if not isinstance(self.source, SnapshotIngestionSource):
            raise ValueError("source must be a SnapshotIngestionSource")
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("sequence must be a positive integer")
        _aware(self.received_at, "received_at")
        if not isinstance(self.currency, str) or re.fullmatch(r"[A-Z]{3}", self.currency) is None:
            raise ValueError("currency must be a three-letter ISO code")
        if not isinstance(self.snapshot, PropFirmAccountSnapshot):
            raise ValueError("snapshot must be a PropFirmAccountSnapshot")


@dataclass(frozen=True)
class SnapshotCursor:
    tenant_id: str
    account_id: str
    source_id: str
    source_version: str
    profile_config_hash: str
    currency: str
    sequence: int
    captured_at: datetime
    payload_hash: str

    def __post_init__(self) -> None:
        TenantIdentity(self.tenant_id)
        AccountIdentity(self.tenant_id, self.account_id)
        for name in ("source_id", "source_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"{name} must be a safe identifier")
        if not isinstance(self.profile_config_hash, str) or re.fullmatch(
            r"[0-9a-f]{64}", self.profile_config_hash
        ) is None:
            raise ValueError("profile_config_hash must be a lowercase sha256 digest")
        if not isinstance(self.currency, str) or re.fullmatch(r"[A-Z]{3}", self.currency) is None:
            raise ValueError("currency must be a three-letter ISO code")
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("sequence must be a positive integer")
        _aware(self.captured_at, "captured_at")
        if not isinstance(self.payload_hash, str) or re.fullmatch(
            r"[0-9a-f]{64}", self.payload_hash
        ) is None:
            raise ValueError("payload_hash must be a lowercase sha256 digest")


@dataclass(frozen=True)
class SnapshotIngestionDecision:
    accepted: bool
    duplicate: bool
    code: IngestionCode
    blocking_reasons: tuple[str, ...] = ()
    next_cursor: SnapshotCursor | None = None
    canonical_admin_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if type(self.accepted) is not bool or type(self.duplicate) is not bool:
            raise ValueError("accepted and duplicate must be boolean")
        if not isinstance(self.code, IngestionCode):
            raise ValueError("code must be an IngestionCode")
        if not isinstance(self.blocking_reasons, tuple):
            raise ValueError("blocking_reasons must be an immutable tuple")
        if tuple(sorted(set(self.blocking_reasons))) != self.blocking_reasons:
            raise ValueError("blocking_reasons must be sorted and unique")
        if self.accepted != (self.code is IngestionCode.ACCEPTED):
            raise ValueError("accepted state does not match code")
        if self.duplicate != (self.code is IngestionCode.DUPLICATE_IDEMPOTENT):
            raise ValueError("duplicate state does not match code")
        if (self.accepted or self.duplicate) != (self.next_cursor is not None):
            raise ValueError("only accepted or idempotent results carry a cursor")


def _decision(
    code: IngestionCode,
    *reasons: str,
    cursor: SnapshotCursor | None = None,
) -> SnapshotIngestionDecision:
    return SnapshotIngestionDecision(
        accepted=code is IngestionCode.ACCEPTED,
        duplicate=code is IngestionCode.DUPLICATE_IDEMPOTENT,
        code=code,
        blocking_reasons=tuple(sorted(set(reasons))),
        next_cursor=cursor,
    )


def _missing_financial_fields(snapshot: PropFirmAccountSnapshot) -> tuple[str, ...]:
    state = snapshot.state
    required = (
        "account_started_at", "starting_balance", "current_balance",
        "current_equity", "realized_pnl", "unrealized_pnl", "daily_pnl",
        "highest_balance", "highest_equity", "highest_end_of_day_balance",
        "prior_end_of_day_balance", "contracts_open", "working_orders",
        "contracts_traded", "exposures", "trading_days", "best_day_profit",
        "total_profit", "withdrawals", "prior_payout_count", "payout_cycle",
    )
    missing = [name for name in required if getattr(state, name) is None]
    if state.payout_cycle is not None:
        cycle_required = (
            "cycle_id", "payout_count", "profit_since_last_payout",
            "winning_days_since_last_payout", "trading_days_since_last_payout",
            "current_cycle_start", "withdrawals_total",
            "best_day_profit_since_last_payout",
        )
        missing.extend(
            f"payout_cycle.{name}"
            for name in cycle_required
            if getattr(state.payout_cycle, name) is None
        )
    return tuple(sorted(missing))


def _inconsistent_financial_fields(
    snapshot: PropFirmAccountSnapshot,
) -> tuple[str, ...]:
    state = snapshot.state
    reasons: list[str] = []
    if state.highest_balance is not None and state.current_balance is not None:
        if state.highest_balance < state.current_balance:
            reasons.append("highest_balance_below_current_balance")
    if state.highest_equity is not None and state.current_equity is not None:
        if state.highest_equity < state.current_equity:
            reasons.append("highest_equity_below_current_equity")
    if (
        state.highest_end_of_day_balance is not None
        and state.prior_end_of_day_balance is not None
        and state.highest_end_of_day_balance < state.prior_end_of_day_balance
    ):
        reasons.append("highest_eod_below_prior_eod")
    if state.exposures is not None:
        keys = [(item.instrument, item.product_group) for item in state.exposures]
        if len(keys) != len(set(keys)):
            reasons.append("duplicate_exposure")
    return tuple(sorted(reasons))


def evaluate_snapshot_ingestion(
    request: SnapshotIngestionRequest,
    *,
    now: datetime,
    freshness: SnapshotFreshnessPolicy,
    previous: SnapshotCursor | None = None,
) -> SnapshotIngestionDecision:
    """Validate one snapshot without writing or mutating any runtime state."""
    if not isinstance(request, SnapshotIngestionRequest):
        raise ValueError("request must be a SnapshotIngestionRequest")
    _aware(now, "now")
    if not isinstance(freshness, SnapshotFreshnessPolicy):
        raise ValueError("freshness must be a SnapshotFreshnessPolicy")
    if previous is not None and not isinstance(previous, SnapshotCursor):
        raise ValueError("previous must be a SnapshotCursor")

    snapshot = request.snapshot
    if snapshot.account_id != request.account.account_id:
        return _decision(IngestionCode.IDENTITY_MISMATCH, "account_id")
    if any((
        snapshot.firm_id != request.profile.firm_id,
        snapshot.program_id != request.profile.program_id,
        snapshot.stage.value != request.profile.stage,
        snapshot.account_size != request.profile.account_size.value,
        snapshot.profile_version != request.profile.profile_version,
        request.profile.account_size.unit is not DecimalUnit.CURRENCY,
        request.profile.account_size.currency != request.currency,
    )):
        return _decision(IngestionCode.PROFILE_MISMATCH, "profile_identity")
    if any((
        snapshot.data_source != request.source.identity.source_id,
        snapshot.simulated != request.source.identity.simulated,
        request.source.kind is SnapshotSourceKind.PAPER and not snapshot.simulated,
    )):
        return _decision(IngestionCode.SOURCE_MISMATCH, "source_identity")

    missing = _missing_financial_fields(snapshot)
    if missing:
        return _decision(IngestionCode.INCOMPLETE_FINANCIAL_STATE, *missing)
    inconsistent = _inconsistent_financial_fields(snapshot)
    if inconsistent:
        return _decision(IngestionCode.INCONSISTENT_FINANCIAL_STATE, *inconsistent)

    skew = timedelta(seconds=freshness.maximum_future_skew_seconds)
    if snapshot.captured_at - now > skew:
        return _decision(IngestionCode.FUTURE_SNAPSHOT, "captured_at")
    if now - snapshot.captured_at > timedelta(seconds=freshness.maximum_age_seconds):
        return _decision(IngestionCode.STALE_SNAPSHOT, "captured_at")
    if request.received_at + skew < snapshot.captured_at or request.received_at - now > skew:
        return _decision(IngestionCode.INVALID_RECEIPT_TIME, "received_at")

    cursor = SnapshotCursor(
        tenant_id=request.tenant.tenant_id,
        account_id=request.account.account_id,
        source_id=request.source.identity.source_id,
        source_version=request.source.identity.source_version,
        profile_config_hash=request.profile.config_hash,
        currency=request.currency,
        sequence=request.sequence,
        captured_at=snapshot.captured_at,
        payload_hash=snapshot.content_hash,
    )
    if previous is None:
        return _decision(IngestionCode.ACCEPTED, cursor=cursor)
    if (
        previous.tenant_id != cursor.tenant_id
        or previous.account_id != cursor.account_id
        or previous.source_id != cursor.source_id
        or previous.source_version != cursor.source_version
        or previous.profile_config_hash != cursor.profile_config_hash
        or previous.currency != cursor.currency
    ):
        return _decision(IngestionCode.CURSOR_SCOPE_MISMATCH, "previous_cursor")
    if request.sequence < previous.sequence:
        return _decision(IngestionCode.OUT_OF_ORDER_SEQUENCE, "sequence")
    if request.sequence == previous.sequence:
        if snapshot.content_hash == previous.payload_hash:
            return _decision(IngestionCode.DUPLICATE_IDEMPOTENT, cursor=previous)
        return _decision(IngestionCode.DUPLICATE_CONFLICT, "sequence_hash_conflict")
    if snapshot.captured_at <= previous.captured_at:
        return _decision(IngestionCode.OUT_OF_ORDER_TIMESTAMP, "captured_at")
    return _decision(IngestionCode.ACCEPTED, cursor=cursor)
