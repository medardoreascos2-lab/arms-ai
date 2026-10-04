"""In-process emulation of Phase 6 external staging dependencies."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import hashlib
import re
from types import MappingProxyType
from typing import Mapping


class ProviderDependency(str, Enum):
    DATABASE = "database"
    SECRETS = "secrets"
    IDENTITY = "identity"
    METRICS = "metrics"
    REGISTRY = "registry"
    BACKUP = "backup"


class ProviderEmulationError(RuntimeError):
    """Base error for invalid or unavailable local provider emulation."""


class ProviderDependencyUnavailable(ProviderEmulationError):
    """Raised when a required emulated dependency is intentionally unavailable."""


@dataclass(frozen=True)
class EmulatedSecretResolution:
    reference: str
    version: str
    material_fingerprint: str
    synthetic: bool = True
    plaintext_exposed: bool = False


@dataclass(frozen=True)
class EmulatedIdentityMetadata:
    issuer: str
    audience: str
    jwks_uri: str
    tenant: str
    synthetic: bool = True


@dataclass(frozen=True)
class EmulatedMetricRecord:
    name: str
    value: Decimal
    labels: Mapping[str, str]


@dataclass(frozen=True)
class EmulatedBackupObject:
    key: str
    sha256: str
    size_bytes: int
    encrypted: bool = True


class LocalProviderEmulator:
    """Deterministic local-only adapter surface; it never performs I/O or auth."""

    database_endpoint = "emulator+postgresql://database.phase6.invalid:5432/arms_staging"
    metrics_endpoint = "emulator+https://metrics.phase6.invalid/v1/ingest"
    registry_endpoint = "emulator+oci://registry.phase6.invalid/arms-ai-staging"
    backup_endpoint = "emulator+s3://backup.phase6.invalid/backups"
    identity_metadata = EmulatedIdentityMetadata(
        issuer="https://identity.phase6.invalid/",
        audience="arms-ai-staging",
        jwks_uri="https://identity.phase6.invalid/.well-known/jwks.json",
        tenant="synthetic-phase6-tenant",
    )

    def __init__(self) -> None:
        self._availability = {dependency: True for dependency in ProviderDependency}
        self._metrics: list[EmulatedMetricRecord] = []
        self._backups: dict[str, EmulatedBackupObject] = {}
        self.credentials_loaded = False
        self.network_calls = 0
        self.external_mutations = 0
        self.execution_authorized = False

    def set_available(self, dependency: ProviderDependency, available: bool) -> None:
        if not isinstance(dependency, ProviderDependency) or not isinstance(available, bool):
            raise ValueError("dependency and availability must be explicit")
        self._availability[dependency] = available

    def _require(self, dependency: ProviderDependency) -> None:
        if not self._availability[dependency]:
            raise ProviderDependencyUnavailable(f"{dependency.value} emulator is unavailable")

    def resolve_database_endpoint(self) -> str:
        self._require(ProviderDependency.DATABASE)
        return self.database_endpoint

    def resolve_secret(self, reference: str) -> EmulatedSecretResolution:
        self._require(ProviderDependency.SECRETS)
        if not isinstance(reference, str) or not re.fullmatch(
            r"arn:aws:secretsmanager:phase6-local:000000000000:secret:arms-ai/staging/[a-z-]+",
            reference,
        ):
            raise ProviderEmulationError("secret lookup requires an approved synthetic reference")
        fingerprint = hashlib.sha256(f"phase6-emulated:{reference}".encode("utf-8")).hexdigest()
        return EmulatedSecretResolution(reference, "synthetic-v1", fingerprint)

    def resolve_identity_metadata(self) -> EmulatedIdentityMetadata:
        self._require(ProviderDependency.IDENTITY)
        return self.identity_metadata

    def emit_metric(
        self,
        name: str,
        value: Decimal,
        labels: Mapping[str, str],
    ) -> EmulatedMetricRecord:
        self._require(ProviderDependency.METRICS)
        if not isinstance(name, str) or not name.strip():
            raise ProviderEmulationError("metric name must be nonempty")
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ProviderEmulationError("metric value must be a finite Decimal")
        safe_labels = dict(labels)
        if any(not isinstance(key, str) or not isinstance(item, str) for key, item in safe_labels.items()):
            raise ProviderEmulationError("metric labels must be text")
        if any(marker in key.lower() for key in safe_labels for marker in ("secret", "token", "password")):
            raise ProviderEmulationError("secret-bearing metric labels are forbidden")
        record = EmulatedMetricRecord(name.strip(), value, MappingProxyType(safe_labels))
        self._metrics.append(record)
        return record

    def resolve_artifact(self, digest: str) -> str:
        self._require(ProviderDependency.REGISTRY)
        if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise ProviderEmulationError("artifact must use a complete sha256 digest")
        return f"{self.registry_endpoint}@{digest}"

    def store_backup(self, key: str, payload: bytes) -> EmulatedBackupObject:
        self._require(ProviderDependency.BACKUP)
        if not isinstance(key, str) or not re.fullmatch(r"backups/[a-zA-Z0-9._/-]+", key):
            raise ProviderEmulationError("backup key must remain inside the backups prefix")
        if not isinstance(payload, bytes) or not payload:
            raise ProviderEmulationError("backup payload must be nonempty bytes")
        record = EmulatedBackupObject(key, hashlib.sha256(payload).hexdigest(), len(payload))
        self._backups[key] = record
        return record

    @property
    def metrics(self) -> tuple[EmulatedMetricRecord, ...]:
        return tuple(self._metrics)

    @property
    def backups(self) -> Mapping[str, EmulatedBackupObject]:
        return MappingProxyType(dict(self._backups))

    @property
    def availability(self) -> Mapping[ProviderDependency, bool]:
        return MappingProxyType(dict(self._availability))
