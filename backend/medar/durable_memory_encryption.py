"""Provider-neutral authenticated memory encryption contract.

The concrete local provider reuses the existing Phase 5 test-only cipher.
It is never production encryption and never handles real personal secrets.
"""

import base64
import binascii
import hashlib
import json
import os
from secrets import token_hex
from dataclasses import dataclass, field
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.phase5.encrypted_backup import (
    EphemeralStagingBackupKey, LocalEphemeralBackupCipher,
    StagingBackupEncryptionError,
)


_TEST_FORMAT = "arms.medar.memory.local-test.v1"


@dataclass(frozen=True)
class EncryptedMemoryPayload:
    ciphertext: bytes = field(repr=False)
    algorithm_identifier: str
    key_reference: str
    key_version: str
    nonce_metadata: str
    associated_data_hash: str
    authenticated: bool
    local_test_only: bool

    def __post_init__(self) -> None:
        if not isinstance(self.ciphertext, bytes) or not self.ciphertext:
            raise ValueError("encrypted payload ciphertext is required")
        for name in ("algorithm_identifier", "key_reference", "key_version", "nonce_metadata", "associated_data_hash"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.authenticated, bool) or not isinstance(self.local_test_only, bool):
            raise TypeError("encryption classification must be boolean")


class DurableMemoryEncryptionProvider(Protocol):
    algorithm_identifier: str
    key_reference: str
    key_version: str
    production_ready: bool
    local_test_only: bool

    def encrypt(self, plaintext: bytes, *, associated_data: bytes) -> EncryptedMemoryPayload: ...
    def decrypt(self, payload: EncryptedMemoryPayload, *, associated_data: bytes) -> bytes: ...
    def close(self) -> None: ...


class DisabledDurableMemoryEncryption:
    algorithm_identifier = "DISABLED"
    key_reference = "NONE"
    key_version = "NONE"
    production_ready = False
    local_test_only = False

    def encrypt(self, plaintext: bytes, *, associated_data: bytes) -> EncryptedMemoryPayload:
        raise PermissionError("durable memory encryption unavailable")

    def decrypt(self, payload: EncryptedMemoryPayload, *, associated_data: bytes) -> bytes:
        raise PermissionError("durable memory encryption unavailable")

    def close(self) -> None:
        pass


class EphemeralTestMemoryEncryption:
    """Synthetic-only wrapper around the existing Phase 5 local test cipher."""

    production_ready = False
    local_test_only = True

    def __init__(self, *, local_test_enabled: bool = False, key_version: str = "ephemeral-1"):
        if not local_test_enabled:
            raise PermissionError("ephemeral encryption requires explicit local-test enablement")
        if not isinstance(key_version, str) or not key_version.strip():
            raise ValueError("key_version is required")
        self._key = EphemeralStagingBackupKey.generate(local_test_enabled=True)
        self._cipher = LocalEphemeralBackupCipher(self._key, local_test_enabled=True)
        self.algorithm_identifier = self._cipher.algorithm
        self.key_reference = self._key.key_id
        self.key_version = key_version

    @staticmethod
    def _validate_input(data: bytes, name: str, maximum: int) -> None:
        if not isinstance(data, bytes) or not data or len(data) > maximum:
            raise ValueError(f"{name} must be bounded non-empty bytes")

    def encrypt(self, plaintext: bytes, *, associated_data: bytes) -> EncryptedMemoryPayload:
        self._validate_input(plaintext, "plaintext", 64 * 1024)
        self._validate_input(associated_data, "associated_data", 4096)
        aad_hash = hashlib.sha256(associated_data).hexdigest()
        inner = json.dumps({
            "format": _TEST_FORMAT,
            "associated_data_hash": aad_hash,
            "plaintext": base64.b64encode(plaintext).decode("ascii"),
        }, sort_keys=True, separators=(",", ":")).encode("ascii")
        ciphertext = self._cipher.encrypt(inner)
        nonce = json.loads(ciphertext)["nonce"]
        return EncryptedMemoryPayload(
            ciphertext, self.algorithm_identifier, self.key_reference,
            self.key_version, nonce, aad_hash, True, True,
        )

    def decrypt(self, payload: EncryptedMemoryPayload, *, associated_data: bytes) -> bytes:
        self._validate_input(associated_data, "associated_data", 4096)
        if not isinstance(payload, EncryptedMemoryPayload) or (
            payload.algorithm_identifier != self.algorithm_identifier
            or payload.key_reference != self.key_reference
            or payload.key_version != self.key_version
            or payload.associated_data_hash != hashlib.sha256(associated_data).hexdigest()
            or not payload.authenticated or not payload.local_test_only
        ):
            raise PermissionError("memory encryption metadata mismatch")
        try:
            document = json.loads(payload.ciphertext)
            if document["nonce"] != payload.nonce_metadata:
                raise ValueError("nonce metadata mismatch")
            inner_bytes = self._cipher.decrypt(payload.ciphertext)
            inner = json.loads(inner_bytes)
            if set(inner) != {"format", "associated_data_hash", "plaintext"} or (
                inner["format"] != _TEST_FORMAT
                or inner["associated_data_hash"] != payload.associated_data_hash
            ):
                raise ValueError("encrypted content context mismatch")
            encoded = inner["plaintext"]
            plaintext = base64.b64decode(encoded, validate=True)
            if base64.b64encode(plaintext).decode("ascii") != encoded or not plaintext:
                raise ValueError("invalid encrypted content")
            return plaintext
        except (StagingBackupEncryptionError, UnicodeError, ValueError, KeyError, TypeError, binascii.Error) as exc:
            raise PermissionError("memory ciphertext authentication failed") from exc

    def close(self) -> None:
        self._key.close()

    def __enter__(self) -> "EphemeralTestMemoryEncryption":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class AESGCMEphemeralMemoryEncryption:
    """AES-256-GCM with a process-local synthetic key for Phase 8 development."""

    algorithm_identifier = "AES-256-GCM"
    production_ready = False
    local_test_only = True
    sensitive_local_development_ready = True

    def __init__(
        self,
        *,
        local_development_enabled: bool = False,
        key_version: str = "dev-1",
    ) -> None:
        if not local_development_enabled:
            raise PermissionError("AES-GCM requires explicit local-development enablement")
        if not isinstance(key_version, str) or not key_version.strip() or len(key_version) > 64:
            raise ValueError("key_version must be bounded non-empty text")
        self.key_reference = "ephemeral-aesgcm-" + token_hex(16)
        self.key_version = key_version
        self._key = bytearray(AESGCM.generate_key(bit_length=256))
        self._closed = False

    @staticmethod
    def _validate_input(data: bytes, name: str, maximum: int) -> None:
        if not isinstance(data, bytes) or not data or len(data) > maximum:
            raise ValueError(f"{name} must be bounded non-empty bytes")

    def _require_open(self) -> None:
        if self._closed or not self._key:
            raise PermissionError("AES-GCM key is unavailable")

    def encrypt(self, plaintext: bytes, *, associated_data: bytes) -> EncryptedMemoryPayload:
        self._require_open()
        self._validate_input(plaintext, "plaintext", 64 * 1024)
        self._validate_input(associated_data, "associated_data", 4096)
        nonce = os.urandom(12)
        ciphertext = AESGCM(bytes(self._key)).encrypt(nonce, plaintext, associated_data)
        return EncryptedMemoryPayload(
            ciphertext=ciphertext,
            algorithm_identifier=self.algorithm_identifier,
            key_reference=self.key_reference,
            key_version=self.key_version,
            nonce_metadata=base64.b64encode(nonce).decode("ascii"),
            associated_data_hash=hashlib.sha256(associated_data).hexdigest(),
            authenticated=True,
            local_test_only=True,
        )

    def decrypt(self, payload: EncryptedMemoryPayload, *, associated_data: bytes) -> bytes:
        self._require_open()
        self._validate_input(associated_data, "associated_data", 4096)
        if not isinstance(payload, EncryptedMemoryPayload) or (
            payload.algorithm_identifier != self.algorithm_identifier
            or payload.key_reference != self.key_reference
            or payload.key_version != self.key_version
            or payload.associated_data_hash != hashlib.sha256(associated_data).hexdigest()
            or not payload.authenticated
            or not payload.local_test_only
        ):
            raise PermissionError("AES-GCM memory metadata mismatch")
        try:
            nonce = base64.b64decode(payload.nonce_metadata, validate=True)
            if len(nonce) != 12 or base64.b64encode(nonce).decode("ascii") != payload.nonce_metadata:
                raise ValueError("invalid AES-GCM nonce")
            if len(payload.ciphertext) < 17:
                raise ValueError("truncated AES-GCM ciphertext")
            return AESGCM(bytes(self._key)).decrypt(nonce, payload.ciphertext, associated_data)
        except (InvalidTag, ValueError, TypeError, binascii.Error) as exc:
            raise PermissionError("AES-GCM memory authentication failed") from exc

    def close(self) -> None:
        if not self._closed:
            for index in range(len(self._key)):
                self._key[index] = 0
            self._key.clear()
            self._closed = True

    def __enter__(self) -> "AESGCMEphemeralMemoryEncryption":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
