"""Durable, append-only repository for read-only prop-firm evaluations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import hmac
import json
import re
import sqlite3
from typing import NoReturn

from backend.prop_firms import (
    AccountEvaluationV2,
    RuleOutcome,
    RuleScope,
    RuleStatus,
    SourceStatus,
)

from .durable_store import (
    DurableStoreIntegrityError,
    DurableStoreReadOnlyError,
    Phase3DurableStateStore,
    _canonical_utc,
    _parse_canonical_utc,
)
from .snapshot_repository import (
    AccountSnapshotRepository,
    SnapshotRepositoryIntegrityError,
    StoredAccountSnapshot,
    _decode_value,
    _encode_value,
)


EVALUATION_SERIALIZATION_FORMAT = "arms.phase3.prop-firm-evaluation-json.v1"
MAX_EVALUATION_BYTES = 1_048_576
_HASH = re.compile(r"^[0-9a-f]{64}$")


class EvaluationRepositoryError(RuntimeError):
    """Base evaluation repository failure."""


class EvaluationRepositoryConflictError(EvaluationRepositoryError):
    """An immutable evaluation identity conflicts with stored evidence."""


class EvaluationRepositoryRejectedError(EvaluationRepositoryError):
    """The evaluation does not match its durable snapshot evidence."""


class EvaluationRepositoryIntegrityError(EvaluationRepositoryError):
    """Stored evaluation evidence failed strict validation."""


def _reject_float(_: str) -> NoReturn:
    raise ValueError("evaluation JSON floating-point numbers are forbidden")


def _reject_constant(_: str) -> NoReturn:
    raise ValueError("evaluation JSON non-finite numbers are forbidden")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate evaluation JSON field: {key}")
        result[key] = value
    return result


def _object(value: object, keys: frozenset[str], name: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{name} must contain exactly the required fields")
    return value


def _encode_pairs(values: tuple[tuple[str, object], ...]) -> list[object]:
    if not isinstance(values, tuple):
        raise ValueError("named values must be an immutable tuple")
    result = []
    names = set()
    for entry in values:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise ValueError("named values must contain pairs")
        name, value = entry
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("named value keys must be unique nonempty text")
        names.add(name)
        result.append({"name": name, "value": _encode_value(value)})
    return result


def _validate_evaluation(evaluation: AccountEvaluationV2) -> None:
    if not isinstance(evaluation, AccountEvaluationV2):
        raise ValueError("evaluation must be an AccountEvaluationV2")
    for name in (
        "account_valid", "account_failed", "trading_allowed_now",
        "stage_objective_met", "payout_eligible",
    ):
        if type(getattr(evaluation, name)) is not bool:
            raise ValueError(f"{name} must be a boolean")
    for name in ("warnings", "blocking_reasons", "failure_reasons"):
        value = getattr(evaluation, name)
        if not isinstance(value, tuple) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"{name} must be an immutable string tuple")
    if not isinstance(evaluation.outcomes, tuple):
        raise ValueError("outcomes must be an immutable tuple")
    for outcome in evaluation.outcomes:
        if (
            not isinstance(outcome, RuleOutcome)
            or not isinstance(outcome.rule_id, str)
            or not outcome.rule_id
            or not isinstance(outcome.scope, RuleScope)
            or not isinstance(outcome.status, RuleStatus)
            or not isinstance(outcome.reason, str)
            or not isinstance(outcome.evidence, tuple)
            or (outcome.reset_at is not None and (
                not isinstance(outcome.reset_at, datetime)
                or outcome.reset_at.tzinfo is None
                or outcome.reset_at.utcoffset() is None
            ))
        ):
            raise ValueError("evaluation contains an invalid rule outcome")
        _encode_pairs(outcome.evidence)
    if not isinstance(evaluation.metrics, tuple):
        raise ValueError("metrics must be an immutable tuple")
    _encode_pairs(evaluation.metrics)
    if (
        not isinstance(evaluation.profile_identity, str)
        or not evaluation.profile_identity
        or not isinstance(evaluation.rule_version, str)
        or not evaluation.rule_version
        or (
            evaluation.source_status is not None
            and not isinstance(evaluation.source_status, SourceStatus)
        )
    ):
        raise ValueError("evaluation identity or source status is invalid")


def _decode_pairs(value: object, name: str) -> tuple[tuple[str, object], ...]:
    if not isinstance(value, list) or len(value) > 10_000:
        raise ValueError(f"{name} must be a bounded list")
    result: list[tuple[str, object]] = []
    for index, raw in enumerate(value):
        item = _object(raw, frozenset({"name", "value"}), f"{name}[{index}]")
        key = item["name"]
        if not isinstance(key, str) or not key:
            raise ValueError(f"{name}[{index}].name must be nonempty text")
        result.append((key, _decode_value(item["value"], f"{name}[{index}].value")))
    if len({key for key, _ in result}) != len(result):
        raise ValueError(f"{name} names must be unique")
    return tuple(result)


def _outcome_document(outcome: RuleOutcome) -> dict[str, object]:
    return {
        "evidence": _encode_pairs(outcome.evidence),
        "reason": outcome.reason,
        "reset_at": _encode_value(outcome.reset_at),
        "rule_id": outcome.rule_id,
        "scope": outcome.scope.value,
        "status": outcome.status.value,
    }


def _decode_outcome(value: object, index: int) -> RuleOutcome:
    item = _object(
        value,
        frozenset({"evidence", "reason", "reset_at", "rule_id", "scope", "status"}),
        f"outcomes[{index}]",
    )
    try:
        return RuleOutcome(
            rule_id=item["rule_id"],
            scope=RuleScope(item["scope"]),
            status=RuleStatus(item["status"]),
            reason=item["reason"],
            evidence=_decode_pairs(item["evidence"], f"outcomes[{index}].evidence"),
            reset_at=_decode_value(item["reset_at"], f"outcomes[{index}].reset_at"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"outcomes[{index}] is invalid") from exc


def serialize_evaluation(evaluation: AccountEvaluationV2) -> bytes:
    _validate_evaluation(evaluation)
    document = {
        "account_failed": evaluation.account_failed,
        "account_valid": evaluation.account_valid,
        "blocking_reasons": list(evaluation.blocking_reasons),
        "failure_reasons": list(evaluation.failure_reasons),
        "format": EVALUATION_SERIALIZATION_FORMAT,
        "metrics": _encode_pairs(evaluation.metrics),
        "outcomes": [_outcome_document(item) for item in evaluation.outcomes],
        "payout_eligible": evaluation.payout_eligible,
        "profile_identity": evaluation.profile_identity,
        "rule_version": evaluation.rule_version,
        "source_status": (
            evaluation.source_status.value if evaluation.source_status is not None else None
        ),
        "stage_objective_met": evaluation.stage_objective_met,
        "trading_allowed_now": evaluation.trading_allowed_now,
        "warnings": list(evaluation.warnings),
    }
    encoded = json.dumps(
        document, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if len(encoded) > MAX_EVALUATION_BYTES:
        raise ValueError("serialized evaluation exceeds size limit")
    return encoded


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be a list of strings")
    return tuple(value)


def deserialize_evaluation(payload: bytes | str) -> AccountEvaluationV2:
    if isinstance(payload, str):
        encoded = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        encoded = payload
    else:
        raise ValueError("evaluation payload must be bytes or text")
    if len(encoded) > MAX_EVALUATION_BYTES:
        raise ValueError("serialized evaluation exceeds size limit")
    try:
        raw = json.loads(
            encoded.decode("utf-8"), object_pairs_hook=_unique_object,
            parse_float=_reject_float, parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, UnicodeEncodeError, json.JSONDecodeError) as exc:
        raise ValueError("evaluation payload is not valid canonical JSON") from exc
    keys = frozenset({
        "account_failed", "account_valid", "blocking_reasons", "failure_reasons",
        "format", "metrics", "outcomes", "payout_eligible", "profile_identity",
        "rule_version", "source_status", "stage_objective_met",
        "trading_allowed_now", "warnings",
    })
    item = _object(raw, keys, "evaluation")
    if item["format"] != EVALUATION_SERIALIZATION_FORMAT:
        raise ValueError("unsupported evaluation serialization format")
    source_value = item["source_status"]
    try:
        source_status = None if source_value is None else SourceStatus(source_value)
        outcomes_raw = item["outcomes"]
        if not isinstance(outcomes_raw, list) or len(outcomes_raw) > 10_000:
            raise ValueError("outcomes must be a bounded list")
        evaluation = AccountEvaluationV2(
            account_valid=item["account_valid"],
            account_failed=item["account_failed"],
            trading_allowed_now=item["trading_allowed_now"],
            stage_objective_met=item["stage_objective_met"],
            payout_eligible=item["payout_eligible"],
            outcomes=tuple(_decode_outcome(value, index) for index, value in enumerate(outcomes_raw)),
            warnings=_string_tuple(item["warnings"], "warnings"),
            blocking_reasons=_string_tuple(item["blocking_reasons"], "blocking_reasons"),
            failure_reasons=_string_tuple(item["failure_reasons"], "failure_reasons"),
            metrics=_decode_pairs(item["metrics"], "metrics"),
            profile_identity=item["profile_identity"],
            rule_version=item["rule_version"],
            source_status=source_status,
        )
        _validate_evaluation(evaluation)
    except (TypeError, ValueError) as exc:
        raise ValueError("evaluation content is invalid") from exc
    if serialize_evaluation(evaluation) != encoded:
        raise ValueError("evaluation payload is not canonical")
    return evaluation


def _profile_identity(snapshot: StoredAccountSnapshot) -> str:
    value = snapshot.snapshot
    return (
        f"{value.firm_id}/{value.program_id}/{value.stage.value}/"
        f"{value.profile_version}/{snapshot.stream.profile_config_hash}"
    )


def _authoritative(evaluation: AccountEvaluationV2) -> bool:
    return (
        evaluation.source_status is SourceStatus.CURRENT_VERIFIED
        and bool(evaluation.outcomes)
        and all(item.status is not RuleStatus.INCOMPLETE_DATA for item in evaluation.outcomes)
    )


@dataclass(frozen=True)
class StoredEvaluation:
    evaluation_id: str
    tenant_id: str
    snapshot_id: str
    account_id: str
    profile_config_hash: str
    evaluated_at: datetime
    stored_at: datetime
    authoritative: bool
    evaluation: AccountEvaluationV2
    storage_hash: str
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    canonical_admin_authorized: bool = field(default=False, init=False)


@dataclass(frozen=True)
class EvaluationAppendResult:
    record: StoredEvaluation
    inserted: bool
    duplicate: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)


_SELECT = """
SELECT evaluations.evaluation_id, evaluations.tenant_id,
       evaluations.snapshot_id, evaluations.account_id,
       evaluations.profile_config_hash, evaluations.evaluated_at,
       evaluations.stored_at, evaluations.authoritative,
       evaluations.source_status, evaluations.payload,
       evaluations.payload_sha256, snapshots.snapshot_hash,
       snapshots.account_id, snapshots.profile_config_hash
FROM phase3_evaluations AS evaluations
JOIN phase3_account_snapshots AS snapshots
  ON snapshots.tenant_id = evaluations.tenant_id
 AND snapshots.snapshot_id = evaluations.snapshot_id
"""


class EvaluationRepository:
    """Persists evaluation evidence without granting execution authority."""

    execution_authorized = False
    production_mutation_authorized = False
    canonical_admin_authorized = False

    def __init__(self, store: Phase3DurableStateStore):
        if not isinstance(store, Phase3DurableStateStore):
            raise ValueError("store must be a Phase3DurableStateStore")
        self.store = store

    def _connection(self) -> sqlite3.Connection:
        return self.store._require_open()

    def _record(self, row: tuple[object, ...]) -> StoredEvaluation:
        (
            evaluation_id, tenant_id, snapshot_id, account_id, profile_hash,
            evaluated_at, stored_at, authoritative, source_status, payload,
            payload_hash, snapshot_hash, snapshot_account_id, snapshot_profile_hash,
        ) = row
        if (
            not isinstance(payload, bytes)
            or not isinstance(payload_hash, str)
            or _HASH.fullmatch(payload_hash) is None
            or not hmac.compare_digest(hashlib.sha256(payload).hexdigest(), payload_hash)
        ):
            raise EvaluationRepositoryIntegrityError("stored evaluation payload hash mismatch")
        try:
            evaluation = deserialize_evaluation(payload)
            evaluated = _parse_canonical_utc(evaluated_at, "evaluated_at")
            stored = _parse_canonical_utc(stored_at, "stored_at")
        except (TypeError, ValueError, DurableStoreIntegrityError) as exc:
            raise EvaluationRepositoryIntegrityError("stored evaluation is invalid") from exc
        expected_source = evaluation.source_status.value if evaluation.source_status else None
        if (
            not all(isinstance(value, str) for value in (
                evaluation_id, tenant_id, snapshot_id, account_id, profile_hash, snapshot_hash
            ))
            or type(authoritative) is not int
            or authoritative not in (0, 1)
            or source_status != expected_source
            or bool(authoritative) != _authoritative(evaluation)
            or account_id != snapshot_account_id
            or profile_hash != snapshot_profile_hash
        ):
            raise EvaluationRepositoryIntegrityError("stored evaluation index mismatch")
        try:
            snapshot = AccountSnapshotRepository(self.store).by_id(
                tenant_id=tenant_id, snapshot_id=snapshot_id
            )
        except SnapshotRepositoryIntegrityError as exc:
            raise EvaluationRepositoryIntegrityError(
                "linked snapshot evidence is invalid"
            ) from exc
        if (
            snapshot is None
            or snapshot.snapshot_hash != snapshot_hash
            or snapshot.stream.account_id != account_id
            or snapshot.stream.profile_config_hash != profile_hash
            or evaluation.profile_identity != _profile_identity(snapshot)
            or evaluation.rule_version != snapshot.snapshot.profile_version
        ):
            raise EvaluationRepositoryIntegrityError(
                "linked snapshot evidence does not match evaluation"
            )
        return StoredEvaluation(
            evaluation_id, tenant_id, snapshot_id, account_id, profile_hash,
            evaluated, stored, bool(authoritative), evaluation, payload_hash,
        )

    def append(
        self,
        *,
        tenant_id: str,
        evaluation_id: str,
        snapshot_id: str,
        evaluation: AccountEvaluationV2,
        evaluated_at: datetime,
        stored_at: datetime,
    ) -> EvaluationAppendResult:
        connection = self._connection()
        if self.store.read_only:
            raise DurableStoreReadOnlyError("phase3 store is read-only")
        if not isinstance(evaluation_id, str) or not evaluation_id.strip():
            raise ValueError("evaluation_id must be nonempty text")
        evaluated_text = _canonical_utc(evaluated_at, "evaluated_at")
        stored_text = _canonical_utc(stored_at, "stored_at")
        if stored_at.astimezone(timezone.utc) < evaluated_at.astimezone(timezone.utc):
            raise ValueError("stored_at cannot precede evaluated_at")
        try:
            snapshot = AccountSnapshotRepository(self.store).by_id(
                tenant_id=tenant_id, snapshot_id=snapshot_id
            )
        except SnapshotRepositoryIntegrityError as exc:
            raise EvaluationRepositoryIntegrityError("snapshot evidence is invalid") from exc
        if snapshot is None:
            raise EvaluationRepositoryRejectedError("snapshot evidence was not found")
        _validate_evaluation(evaluation)
        if evaluation.profile_identity != _profile_identity(snapshot):
            raise EvaluationRepositoryRejectedError("evaluation profile does not match snapshot")
        if evaluation.rule_version != snapshot.snapshot.profile_version:
            raise EvaluationRepositoryRejectedError("evaluation rule version does not match snapshot")
        payload = serialize_evaluation(evaluation)
        payload_hash = hashlib.sha256(payload).hexdigest()
        authoritative = int(_authoritative(evaluation))
        source_status = evaluation.source_status.value if evaluation.source_status else None
        values = (
            tenant_id, evaluation_id, snapshot_id, snapshot.stream.account_id,
            snapshot.stream.profile_config_hash, evaluated_text, stored_text,
            authoritative, source_status, payload, payload_hash,
        )
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                _SELECT + " WHERE evaluations.tenant_id = ? AND evaluations.evaluation_id = ?",
                (tenant_id, evaluation_id),
            ).fetchone()
            if existing is not None:
                record = self._record(existing)
                if (
                    record.storage_hash != payload_hash
                    or record.snapshot_id != snapshot_id
                    or record.evaluated_at != evaluated_at
                ):
                    raise EvaluationRepositoryConflictError(
                        "evaluation identity already has different immutable content"
                    )
                connection.execute("COMMIT")
                return EvaluationAppendResult(record, False, True)
            connection.execute(
                """INSERT INTO phase3_evaluations(
                    tenant_id, evaluation_id, snapshot_id, account_id,
                    profile_config_hash, evaluated_at, stored_at, authoritative,
                    source_status, payload, payload_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                values,
            )
            row = connection.execute(
                _SELECT + " WHERE evaluations.tenant_id = ? AND evaluations.evaluation_id = ?",
                (tenant_id, evaluation_id),
            ).fetchone()
            record = self._record(row)
            connection.execute("COMMIT")
            return EvaluationAppendResult(record, True, False)
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise

    def by_id(self, *, tenant_id: str, evaluation_id: str) -> StoredEvaluation | None:
        row = self._connection().execute(
            _SELECT + " WHERE evaluations.tenant_id = ? AND evaluations.evaluation_id = ?",
            (tenant_id, evaluation_id),
        ).fetchone()
        return None if row is None else self._record(row)

    def for_snapshot(self, *, tenant_id: str, snapshot_id: str) -> tuple[StoredEvaluation, ...]:
        rows = self._connection().execute(
            _SELECT + """ WHERE evaluations.tenant_id = ? AND evaluations.snapshot_id = ?
                ORDER BY evaluations.evaluated_at, evaluations.evaluation_id""",
            (tenant_id, snapshot_id),
        ).fetchall()
        return tuple(self._record(row) for row in rows)
