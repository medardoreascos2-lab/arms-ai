"""Immutable, file-backed historical dataset registry for Phase 3 research."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from threading import RLock


MAX_DATASET_BYTES = 4 * 1024 * 1024 * 1024
MAX_DATASET_LINE_BYTES = 16 * 1024 * 1024
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


class DatasetRegistryError(RuntimeError):
    """Base historical dataset registry failure."""


class DatasetUnavailableError(DatasetRegistryError):
    """The requested source file is not currently available and valid."""


class DatasetIntegrityError(DatasetRegistryError):
    """Available bytes do not match their declared immutable identity."""


class DatasetConflictError(DatasetRegistryError):
    """A dataset ID already identifies different immutable content."""


class DatasetWindow(str, Enum):
    ONE_WEEK = "1_WEEK"
    ONE_MONTH = "1_MONTH"
    THREE_MONTHS = "3_MONTHS"
    SIX_MONTHS = "6_MONTHS"
    TWELVE_MONTHS = "12_MONTHS"


class DatasetFileFormat(str, Enum):
    CSV = "CSV"
    JSONL = "JSONL"


class DatasetCertificationStatus(str, Enum):
    AVAILABLE_UNCERTIFIED = "AVAILABLE_UNCERTIFIED"
    CERTIFIED = "CERTIFIED"


class DatasetVerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    MISSING = "MISSING"
    CHANGED = "CHANGED"
    INVALID = "INVALID"


def _text(value: object, name: str, *, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    normalized = value.strip()
    if len(normalized) > 256 or (pattern is not None and pattern.fullmatch(normalized) is None):
        raise ValueError(f"{name} is invalid")
    return normalized


def _aware(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    return _aware(value, "timestamp").isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _canonical_hash(document: dict[str, object]) -> str:
    encoded = json.dumps(
        document, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"duplicate JSON field: {name}")
        result[name] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value is forbidden: {value}")


@dataclass(frozen=True)
class HistoricalDatasetRegistration:
    dataset_id: str
    instrument: str
    contract: str
    timeframe: str
    session_template: str
    starts_at: datetime
    ends_at: datetime
    source: str
    window: DatasetWindow
    file_format: DatasetFileFormat
    expected_bar_count: int
    expected_sha256: str
    certification_status: DatasetCertificationStatus
    certification_reference: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_id", _text(self.dataset_id, "dataset_id", pattern=_ID))
        for name in ("instrument", "contract", "timeframe", "session_template", "source"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        start = _aware(self.starts_at, "starts_at")
        end = _aware(self.ends_at, "ends_at")
        if start >= end:
            raise ValueError("starts_at must precede ends_at")
        object.__setattr__(self, "starts_at", start)
        object.__setattr__(self, "ends_at", end)
        if not isinstance(self.window, DatasetWindow):
            raise ValueError("window must be a DatasetWindow")
        if not isinstance(self.file_format, DatasetFileFormat):
            raise ValueError("file_format must be a DatasetFileFormat")
        if type(self.expected_bar_count) is not int or self.expected_bar_count < 1:
            raise ValueError("expected_bar_count must be a positive integer")
        if not isinstance(self.expected_sha256, str) or _HASH.fullmatch(
            self.expected_sha256
        ) is None:
            raise ValueError("expected_sha256 must be a lowercase sha256 digest")
        if not isinstance(self.certification_status, DatasetCertificationStatus):
            raise ValueError("certification_status must be a DatasetCertificationStatus")
        if self.certification_status is DatasetCertificationStatus.CERTIFIED:
            object.__setattr__(
                self,
                "certification_reference",
                _text(self.certification_reference, "certification_reference"),
            )
        elif self.certification_reference is not None:
            raise ValueError("uncertified datasets cannot claim certification evidence")


@dataclass(frozen=True)
class HistoricalDataset:
    dataset_id: str
    instrument: str
    contract: str
    timeframe: str
    session_template: str
    starts_at: datetime
    ends_at: datetime
    source: str
    window: DatasetWindow
    file_format: DatasetFileFormat
    bar_count: int
    sha256: str
    certification_status: DatasetCertificationStatus
    certification_reference: str | None
    path: Path
    byte_count: int
    registered_at: datetime
    definition_hash: str
    record_hash: str
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    canonical_admin_authorized: bool = field(default=False, init=False)


@dataclass(frozen=True)
class DatasetRegistrationResult:
    record: HistoricalDataset
    inserted: bool
    duplicate: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.inserted == self.duplicate:
            raise ValueError("registration must be inserted or duplicate")


@dataclass(frozen=True)
class DatasetVerification:
    dataset_id: str
    status: DatasetVerificationStatus
    observed_sha256: str | None
    observed_bar_count: int | None
    reasons: tuple[str, ...]
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.reasons != tuple(sorted(set(self.reasons))):
            raise ValueError("verification reasons must be sorted and unique")
        if self.status is DatasetVerificationStatus.VERIFIED and self.reasons:
            raise ValueError("verified datasets cannot have blocking reasons")


@dataclass(frozen=True)
class _FileEvidence:
    sha256: str
    bar_count: int
    byte_count: int


def _file_marker(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ino


def _inspect_file(path: Path, file_format: DatasetFileFormat) -> _FileEvidence:
    if not path.is_file():
        raise DatasetUnavailableError("dataset source is not an available regular file")
    before = _file_marker(path)
    if before[0] < 1:
        raise DatasetUnavailableError("dataset source is empty")
    if before[0] > MAX_DATASET_BYTES:
        raise DatasetUnavailableError("dataset source exceeds the size limit")
    digest = hashlib.sha256()
    rows = 0
    header: tuple[str, ...] | None = None
    with path.open("rb") as handle:
        for line_number, raw in enumerate(handle, start=1):
            digest.update(raw)
            if len(raw) > MAX_DATASET_LINE_BYTES:
                raise DatasetIntegrityError(
                    f"dataset line {line_number} exceeds the size limit"
                )
            try:
                text = raw.decode("utf-8-sig" if line_number == 1 else "utf-8")
            except UnicodeDecodeError as exc:
                raise DatasetIntegrityError("dataset must use valid UTF-8") from exc
            if not text.strip():
                continue
            if file_format is DatasetFileFormat.JSONL:
                try:
                    value = json.loads(
                        text,
                        object_pairs_hook=_unique_json_object,
                        parse_constant=_reject_json_constant,
                    )
                except (json.JSONDecodeError, ValueError) as exc:
                    raise DatasetIntegrityError(
                        f"JSONL row {line_number} is invalid"
                    ) from exc
                if not isinstance(value, dict):
                    raise DatasetIntegrityError("JSONL bars must be JSON objects")
                rows += 1
                continue
            try:
                parsed = next(csv.reader([text], strict=True))
            except (csv.Error, StopIteration) as exc:
                raise DatasetIntegrityError(f"CSV row {line_number} is invalid") from exc
            if header is None:
                header = tuple(item.strip() for item in parsed)
                if not header or any(not item for item in header) or len(set(header)) != len(header):
                    raise DatasetIntegrityError("CSV header must contain unique names")
            elif len(parsed) != len(header):
                raise DatasetIntegrityError(
                    f"CSV row {line_number} does not match the header"
                )
            else:
                rows += 1
    after = _file_marker(path)
    if before != after:
        raise DatasetUnavailableError("dataset source changed while it was inspected")
    if file_format is DatasetFileFormat.CSV and header is None:
        raise DatasetIntegrityError("CSV dataset has no header")
    if rows < 1:
        raise DatasetIntegrityError("dataset contains no bars")
    return _FileEvidence(digest.hexdigest(), rows, before[0])


def _definition(
    registration: HistoricalDatasetRegistration,
    path: Path,
    evidence: _FileEvidence,
) -> dict[str, object]:
    return {
        "bar_count": evidence.bar_count,
        "byte_count": evidence.byte_count,
        "certification_reference": registration.certification_reference,
        "certification_status": registration.certification_status.value,
        "contract": registration.contract,
        "ends_at": _utc_text(registration.ends_at),
        "file_format": registration.file_format.value,
        "instrument": registration.instrument,
        "path": str(path),
        "session_template": registration.session_template,
        "sha256": evidence.sha256,
        "source": registration.source,
        "starts_at": _utc_text(registration.starts_at),
        "timeframe": registration.timeframe,
        "window": registration.window.value,
    }


class HistoricalDatasetRegistry:
    """Append-only registry that accepts only currently available verified files."""

    execution_authorized = False
    production_mutation_authorized = False
    canonical_admin_authorized = False

    def __init__(self, allowed_roots: tuple[Path, ...]):
        if not isinstance(allowed_roots, tuple) or not allowed_roots:
            raise ValueError("allowed_roots must be a nonempty immutable tuple")
        roots = []
        for raw in allowed_roots:
            if not isinstance(raw, Path):
                raise ValueError("allowed roots must be pathlib.Path values")
            try:
                root = raw.resolve(strict=True)
            except OSError as exc:
                raise ValueError("allowed root must exist") from exc
            if not root.is_dir():
                raise ValueError("allowed root must be a directory")
            roots.append(root)
        self._roots = tuple(sorted(set(roots), key=str))
        self._records: dict[str, HistoricalDataset] = {}
        self._lock = RLock()

    def _path(self, raw: Path) -> Path:
        if not isinstance(raw, Path):
            raise ValueError("path must be a pathlib.Path")
        if raw.is_symlink():
            raise DatasetUnavailableError("dataset source cannot be a symbolic link")
        try:
            path = raw.resolve(strict=True)
        except OSError as exc:
            raise DatasetUnavailableError("dataset source is unavailable") from exc
        if not any(path == root or root in path.parents for root in self._roots):
            raise DatasetUnavailableError("dataset source is outside allowed roots")
        return path

    def register(
        self,
        registration: HistoricalDatasetRegistration,
        *,
        path: Path,
        registered_at: datetime,
    ) -> DatasetRegistrationResult:
        if not isinstance(registration, HistoricalDatasetRegistration):
            raise ValueError("registration must be a HistoricalDatasetRegistration")
        registered = _aware(registered_at, "registered_at")
        resolved = self._path(path)
        evidence = _inspect_file(resolved, registration.file_format)
        if evidence.sha256 != registration.expected_sha256:
            raise DatasetIntegrityError("dataset sha256 does not match registration")
        if evidence.bar_count != registration.expected_bar_count:
            raise DatasetIntegrityError("dataset bar count does not match registration")
        definition = _definition(registration, resolved, evidence)
        definition_hash = _canonical_hash(definition)
        with self._lock:
            existing = self._records.get(registration.dataset_id)
            if existing is not None:
                if existing.definition_hash != definition_hash:
                    raise DatasetConflictError(
                        "dataset ID already identifies different immutable content"
                    )
                return DatasetRegistrationResult(existing, False, True)
            record_hash = _canonical_hash({
                "dataset_id": registration.dataset_id,
                "definition_hash": definition_hash,
                "registered_at": _utc_text(registered),
            })
            record = HistoricalDataset(
                dataset_id=registration.dataset_id,
                instrument=registration.instrument,
                contract=registration.contract,
                timeframe=registration.timeframe,
                session_template=registration.session_template,
                starts_at=registration.starts_at,
                ends_at=registration.ends_at,
                source=registration.source,
                window=registration.window,
                file_format=registration.file_format,
                bar_count=evidence.bar_count,
                sha256=evidence.sha256,
                certification_status=registration.certification_status,
                certification_reference=registration.certification_reference,
                path=resolved,
                byte_count=evidence.byte_count,
                registered_at=registered,
                definition_hash=definition_hash,
                record_hash=record_hash,
            )
            self._records[record.dataset_id] = record
            return DatasetRegistrationResult(record, True, False)

    def get(self, dataset_id: str) -> HistoricalDataset | None:
        key = _text(dataset_id, "dataset_id", pattern=_ID)
        with self._lock:
            return self._records.get(key)

    def list(
        self,
        *,
        window: DatasetWindow | None = None,
        certification_status: DatasetCertificationStatus | None = None,
    ) -> tuple[HistoricalDataset, ...]:
        if window is not None and not isinstance(window, DatasetWindow):
            raise ValueError("window must be a DatasetWindow or None")
        if certification_status is not None and not isinstance(
            certification_status, DatasetCertificationStatus
        ):
            raise ValueError("certification_status is invalid")
        with self._lock:
            values = tuple(self._records.values())
        return tuple(sorted((
            item for item in values
            if (window is None or item.window is window)
            and (
                certification_status is None
                or item.certification_status is certification_status
            )
        ), key=lambda item: item.dataset_id))

    def verify(self, dataset_id: str) -> DatasetVerification:
        record = self.get(dataset_id)
        if record is None:
            raise KeyError(dataset_id)
        try:
            resolved = self._path(record.path)
            evidence = _inspect_file(resolved, record.file_format)
        except DatasetUnavailableError:
            return DatasetVerification(
                record.dataset_id, DatasetVerificationStatus.MISSING,
                None, None, ("SOURCE_UNAVAILABLE",),
            )
        except DatasetIntegrityError:
            return DatasetVerification(
                record.dataset_id, DatasetVerificationStatus.INVALID,
                None, None, ("SOURCE_INVALID",),
            )
        reasons = []
        if evidence.sha256 != record.sha256:
            reasons.append("SHA256_CHANGED")
        if evidence.bar_count != record.bar_count:
            reasons.append("BAR_COUNT_CHANGED")
        if evidence.byte_count != record.byte_count:
            reasons.append("BYTE_COUNT_CHANGED")
        status = (
            DatasetVerificationStatus.VERIFIED
            if not reasons else DatasetVerificationStatus.CHANGED
        )
        return DatasetVerification(
            record.dataset_id,
            status,
            evidence.sha256,
            evidence.bar_count,
            tuple(sorted(reasons)),
        )

    def require_verified(self, dataset_id: str) -> HistoricalDataset:
        record = self.get(dataset_id)
        if record is None:
            raise KeyError(dataset_id)
        verification = self.verify(dataset_id)
        if verification.status is not DatasetVerificationStatus.VERIFIED:
            raise DatasetIntegrityError(
                "dataset is not currently verified: "
                + ",".join(verification.reasons)
            )
        return record
