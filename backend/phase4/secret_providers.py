"""Ephemeral secret provider contracts with no cloud or execution authority."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
from typing import Protocol, runtime_checkable


_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")
_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_ENV_PREFIX = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_MAX_SECRET_BYTES = 64 * 1024


class SecretProviderError(RuntimeError):
    """Base error that never contains resolved secret material."""


class SecretNotFoundError(SecretProviderError):
    pass


class SecretProviderUnavailableError(SecretProviderError):
    pass


class SecretMaterialClosedError(SecretProviderError):
    pass


@dataclass(frozen=True)
class SecretReference:
    reference_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.reference_id, str) or _REFERENCE.fullmatch(
            self.reference_id
        ) is None:
            raise ValueError("secret reference must be an opaque identifier")
        if any(marker in self.reference_id for marker in ("://", "@", "=")):
            raise ValueError("secret reference cannot contain a secret value")


class SecretMaterial:
    """Short-lived mutable storage whose display forms are always redacted."""

    __slots__ = ("_buffer", "_closed")

    def __init__(self, value: str):
        if not isinstance(value, str) or not value or "\x00" in value:
            raise SecretProviderError("resolved secret material is invalid")
        encoded = value.encode("utf-8")
        if len(encoded) > _MAX_SECRET_BYTES:
            raise SecretProviderError("resolved secret material exceeds the size limit")
        self._buffer = bytearray(encoded)
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def reveal(self) -> str:
        if self._closed:
            raise SecretMaterialClosedError("secret material is closed")
        return bytes(self._buffer).decode("utf-8")

    def close(self) -> None:
        if not self._closed:
            for index in range(len(self._buffer)):
                self._buffer[index] = 0
            self._closed = True

    def __enter__(self) -> "SecretMaterial":
        if self._closed:
            raise SecretMaterialClosedError("secret material is closed")
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return "SecretMaterial([REDACTED])"

    def __str__(self) -> str:
        return "[REDACTED]"


@runtime_checkable
class SecretProvider(Protocol):
    provider_id: str
    local_test_only: bool
    execution_authorized: bool
    production_mutation_authorized: bool

    def resolve(self, reference: SecretReference) -> SecretMaterial: ...


class EnvironmentSecretProvider:
    provider_id = "environment"
    local_test_only = False
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(
        self,
        *,
        environment: Mapping[str, str] | None = None,
        prefix: str = "ARMS_SECRET_",
    ):
        if not isinstance(prefix, str) or _ENV_PREFIX.fullmatch(prefix) is None:
            raise ValueError("environment prefix must be an uppercase identifier")
        self._environment = os.environ if environment is None else environment
        self._prefix = prefix

    def environment_name(self, reference: SecretReference) -> str:
        if not isinstance(reference, SecretReference):
            raise ValueError("reference must be a SecretReference")
        digest = hashlib.sha256(reference.reference_id.encode("ascii")).hexdigest().upper()
        return f"{self._prefix}{digest}"

    def resolve(self, reference: SecretReference) -> SecretMaterial:
        name = self.environment_name(reference)
        value = self._environment.get(name)
        if value is None:
            raise SecretNotFoundError("environment secret is not configured")
        try:
            return SecretMaterial(value)
        except SecretProviderError:
            raise SecretProviderError("environment secret is invalid") from None


class FileSecretProvider:
    """Read pre-existing fake/local secrets from a dedicated test directory."""

    provider_id = "local_test_file"
    local_test_only = True
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(self, root: Path, *, local_test_enabled: bool = False):
        if not local_test_enabled:
            raise SecretProviderUnavailableError(
                "file secret provider requires explicit local-test enablement"
            )
        if not isinstance(root, Path) or not root.is_absolute():
            raise ValueError("file secret root must be an absolute Path")
        try:
            resolved = root.resolve(strict=True)
        except OSError:
            raise SecretProviderUnavailableError(
                "file secret provider root is unavailable"
            ) from None
        if not resolved.is_dir():
            raise SecretProviderUnavailableError(
                "file secret provider root is unavailable"
            )
        self._root = resolved

    def path_for(self, reference: SecretReference) -> Path:
        if not isinstance(reference, SecretReference):
            raise ValueError("reference must be a SecretReference")
        digest = hashlib.sha256(reference.reference_id.encode("ascii")).hexdigest()
        return self._root / f"{digest}.secret"

    def resolve(self, reference: SecretReference) -> SecretMaterial:
        path = self.path_for(reference)
        try:
            if path.is_symlink() or not path.is_file():
                raise SecretNotFoundError("local test secret is not configured")
            if path.stat().st_size > _MAX_SECRET_BYTES:
                raise SecretProviderError("local test secret exceeds the size limit")
            raw = path.read_bytes()
        except SecretProviderError:
            raise
        except OSError:
            raise SecretProviderError("local test secret could not be read") from None
        try:
            value = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise SecretProviderError("local test secret is not UTF-8") from None
        if value.endswith("\n"):
            value = value[:-1]
            if value.endswith("\r"):
                value = value[:-1]
        try:
            return SecretMaterial(value)
        except SecretProviderError:
            raise SecretProviderError("local test secret is invalid") from None


class DisabledSecretProvider:
    provider_id = "disabled"
    local_test_only = False
    execution_authorized = False
    production_mutation_authorized = False

    def resolve(self, reference: SecretReference) -> SecretMaterial:
        if not isinstance(reference, SecretReference):
            raise ValueError("reference must be a SecretReference")
        raise SecretProviderUnavailableError("secret resolution is disabled")


class FutureCloudSecretProvider:
    """Nonfunctional seam for a future separately authorized cloud adapter."""

    local_test_only = False
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(self, provider_id: str):
        if not isinstance(provider_id, str) or _PROVIDER_ID.fullmatch(provider_id) is None:
            raise ValueError("provider_id must be a lowercase identifier")
        if provider_id in {"disabled", "environment", "local_test_file"}:
            raise ValueError("provider_id is reserved")
        self.provider_id = provider_id

    def resolve(self, reference: SecretReference) -> SecretMaterial:
        if not isinstance(reference, SecretReference):
            raise ValueError("reference must be a SecretReference")
        raise SecretProviderUnavailableError(
            "cloud secret provider is not implemented"
        )
