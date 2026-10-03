"""Authenticated encrypted backup format for isolated Phase 5 staging tests.

The bundled cipher is deliberately limited to local test use. It is a standard-library
test seam, not a production key-management or encryption implementation.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import secrets
from typing import Callable, Protocol, runtime_checkable


STAGING_BACKUP_PAYLOAD_FORMAT = "arms.phase5.staging-backup-payload-json.v1"
ENCRYPTED_STAGING_BACKUP_FORMAT = "arms.phase5.encrypted-staging-backup-json.v1"
LOCAL_TEST_CIPHER_ALGORITHM = "HMAC-SHA256-STREAM-LOCAL-TEST-ONLY-V1"
_MAX_PLAINTEXT_BYTES = 64 * 1024 * 1024
_MAX_ENVELOPE_BYTES = 96 * 1024 * 1024
_KEY_BYTES = 32
_NONCE_BYTES = 32
_DIGEST_BYTES = 32


class StagingBackupEncryptionError(RuntimeError):
    """Fail-closed format or authentication error without secret material."""


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return _utc(value, "created_at").isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("created_at must be canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("created_at must be canonical UTC") from exc
    if _timestamp(parsed) != value:
        raise ValueError("created_at must be canonical UTC")
    return parsed


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_bytes(document: dict[str, object], *, maximum: int) -> bytes:
    encoded = json.dumps(
        document,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > maximum:
        raise ValueError("staging backup document exceeds size limit")
    return encoded


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("staging backup document contains duplicate fields")
        result[key] = value
    return result


def _reject_float(_: str) -> object:
    raise ValueError("floating-point values are forbidden")


def _reject_constant(_: str) -> object:
    raise ValueError("non-finite values are forbidden")


def _load_json(encoded: bytes, *, maximum: int) -> dict[str, object]:
    if not isinstance(encoded, bytes) or not encoded or len(encoded) > maximum:
        raise ValueError("staging backup document is invalid")
    try:
        document = json.loads(
            encoded.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("staging backup document is not valid JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("staging backup document must be an object")
    return document


def _b64_encode(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


def _b64_decode(value: object, name: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be canonical base64")
    try:
        payload = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise ValueError(f"{name} must be canonical base64") from exc
    if _b64_encode(payload) != value:
        raise ValueError(f"{name} must be canonical base64")
    return payload


@dataclass(frozen=True)
class StagingBackupPayload:
    database: bytes = field(repr=False)
    database_schema_version: int
    audit_continuity: bytes = field(repr=False)
    research_provenance: bytes = field(repr=False)
    created_at: datetime
    hash_manifest: tuple[tuple[str, str], ...] = field(init=False)
    payload_id: str = field(init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    production_backup_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        for name in ("database", "audit_continuity", "research_provenance"):
            value = getattr(self, name)
            if not isinstance(value, bytes) or not value:
                raise ValueError(f"{name} must be nonempty bytes")
        total = len(self.database) + len(self.audit_continuity) + len(self.research_provenance)
        if total > _MAX_PLAINTEXT_BYTES:
            raise ValueError("staging backup payload exceeds size limit")
        if type(self.database_schema_version) is not int or self.database_schema_version < 1:
            raise ValueError("database_schema_version must be positive")
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        manifest = (
            ("audit_continuity_sha256", _sha256(self.audit_continuity)),
            ("database_sha256", _sha256(self.database)),
            ("research_provenance_sha256", _sha256(self.research_provenance)),
        )
        object.__setattr__(self, "hash_manifest", manifest)
        object.__setattr__(self, "payload_id", _sha256(_payload_bytes(self, include_id=False)))


def _payload_document(
    payload: StagingBackupPayload,
    *,
    include_id: bool,
) -> dict[str, object]:
    document = {
        "audit_continuity": _b64_encode(payload.audit_continuity),
        "created_at": _timestamp(payload.created_at),
        "database": _b64_encode(payload.database),
        "database_schema_version": payload.database_schema_version,
        "format": STAGING_BACKUP_PAYLOAD_FORMAT,
        "hash_manifest": dict(payload.hash_manifest),
        "research_provenance": _b64_encode(payload.research_provenance),
    }
    if include_id:
        document["payload_id"] = payload.payload_id
    return document


def _payload_bytes(payload: StagingBackupPayload, *, include_id: bool) -> bytes:
    return _json_bytes(
        _payload_document(payload, include_id=include_id),
        maximum=_MAX_ENVELOPE_BYTES,
    )


def serialize_staging_backup_payload(payload: StagingBackupPayload) -> bytes:
    if not isinstance(payload, StagingBackupPayload):
        raise ValueError("payload must be a StagingBackupPayload")
    return _payload_bytes(payload, include_id=True)


def deserialize_staging_backup_payload(encoded: bytes) -> StagingBackupPayload:
    document = _load_json(encoded, maximum=_MAX_ENVELOPE_BYTES)
    required = {
        "audit_continuity",
        "created_at",
        "database",
        "database_schema_version",
        "format",
        "hash_manifest",
        "payload_id",
        "research_provenance",
    }
    if set(document) != required or document["format"] != STAGING_BACKUP_PAYLOAD_FORMAT:
        raise ValueError("staging backup payload fields or format are invalid")
    payload = StagingBackupPayload(
        database=_b64_decode(document["database"], "database"),
        database_schema_version=document["database_schema_version"],
        audit_continuity=_b64_decode(document["audit_continuity"], "audit_continuity"),
        research_provenance=_b64_decode(
            document["research_provenance"], "research_provenance"
        ),
        created_at=_parse_timestamp(document["created_at"]),
    )
    supplied_manifest = document["hash_manifest"]
    if not isinstance(supplied_manifest, dict) or supplied_manifest != dict(payload.hash_manifest):
        raise ValueError("staging backup hash manifest mismatch")
    supplied_id = document["payload_id"]
    if (
        not isinstance(supplied_id, str)
        or not hmac.compare_digest(supplied_id, payload.payload_id)
        or serialize_staging_backup_payload(payload) != encoded
    ):
        raise ValueError("staging backup payload identity or canonical form mismatch")
    return payload


class EphemeralStagingBackupKey:
    """Mutable local-test key material whose display forms are always redacted."""

    __slots__ = ("_buffer", "_closed", "key_id")
    local_test_only = True
    production_key_authorized = False
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(self, material: bytes, *, local_test_enabled: bool = False):
        if not local_test_enabled:
            raise StagingBackupEncryptionError(
                "ephemeral backup keys require explicit local-test enablement"
            )
        if not isinstance(material, bytes) or len(material) != _KEY_BYTES:
            raise StagingBackupEncryptionError("ephemeral backup key must be 256 bits")
        self._buffer = bytearray(material)
        self._closed = False
        self.key_id = _sha256(b"arms-phase5-local-key-id-v1:" + material)

    @classmethod
    def generate(cls, *, local_test_enabled: bool = False) -> "EphemeralStagingBackupKey":
        return cls(secrets.token_bytes(_KEY_BYTES), local_test_enabled=local_test_enabled)

    @property
    def closed(self) -> bool:
        return self._closed

    def _material(self) -> bytes:
        if self._closed:
            raise StagingBackupEncryptionError("ephemeral backup key is closed")
        return bytes(self._buffer)

    def close(self) -> None:
        if not self._closed:
            for index in range(len(self._buffer)):
                self._buffer[index] = 0
            self._closed = True

    def __enter__(self) -> "EphemeralStagingBackupKey":
        self._material()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return "EphemeralStagingBackupKey([REDACTED])"

    def __str__(self) -> str:
        return "[REDACTED]"


@runtime_checkable
class StagingBackupCipher(Protocol):
    algorithm: str
    local_test_only: bool
    production_encryption_authorized: bool
    execution_authorized: bool
    production_mutation_authorized: bool

    def encrypt(self, plaintext: bytes) -> bytes: ...

    def decrypt(self, envelope: bytes) -> bytes: ...


class LocalEphemeralBackupCipher:
    """Authenticated standard-library cipher seam restricted to local staging tests."""

    algorithm = LOCAL_TEST_CIPHER_ALGORITHM
    local_test_only = True
    production_encryption_authorized = False
    execution_authorized = False
    production_mutation_authorized = False
    external_storage_authorized = False

    def __init__(
        self,
        key: EphemeralStagingBackupKey,
        *,
        local_test_enabled: bool = False,
        nonce_factory: Callable[[int], bytes] | None = None,
    ):
        if not local_test_enabled:
            raise StagingBackupEncryptionError(
                "local backup cipher requires explicit local-test enablement"
            )
        if not isinstance(key, EphemeralStagingBackupKey):
            raise ValueError("key must be an EphemeralStagingBackupKey")
        if nonce_factory is not None and not callable(nonce_factory):
            raise ValueError("nonce_factory must be callable")
        key._material()
        self._key = key
        self._nonce_factory = nonce_factory or secrets.token_bytes
        self._used_nonces: set[bytes] = set()

    @staticmethod
    def _xor_stream(material: bytes, nonce: bytes, payload: bytes) -> bytes:
        output = bytearray(len(payload))
        for block_index, offset in enumerate(range(0, len(payload), _DIGEST_BYTES)):
            stream = hmac.new(
                material,
                b"arms-phase5-stream-v1:" + nonce + block_index.to_bytes(8, "big"),
                hashlib.sha256,
            ).digest()
            block = payload[offset : offset + _DIGEST_BYTES]
            for index, value in enumerate(block):
                output[offset + index] = value ^ stream[index]
        return bytes(output)

    @staticmethod
    def _aad(
        *,
        key_id: str,
        nonce: str,
        plaintext_sha256: str,
        plaintext_size: int,
    ) -> bytes:
        return _json_bytes(
            {
                "algorithm": LOCAL_TEST_CIPHER_ALGORITHM,
                "format": ENCRYPTED_STAGING_BACKUP_FORMAT,
                "key_id": key_id,
                "nonce": nonce,
                "plaintext_sha256": plaintext_sha256,
                "plaintext_size": plaintext_size,
            },
            maximum=4096,
        )

    def encrypt(self, plaintext: bytes) -> bytes:
        if not isinstance(plaintext, bytes) or not plaintext:
            raise ValueError("plaintext must be nonempty bytes")
        if len(plaintext) > _MAX_PLAINTEXT_BYTES:
            raise ValueError("plaintext exceeds staging backup size limit")
        material = self._key._material()
        nonce = self._nonce_factory(_NONCE_BYTES)
        if not isinstance(nonce, bytes) or len(nonce) != _NONCE_BYTES:
            raise StagingBackupEncryptionError("nonce factory returned invalid material")
        if nonce in self._used_nonces:
            raise StagingBackupEncryptionError("nonce reuse is forbidden")
        self._used_nonces.add(nonce)
        nonce_text = _b64_encode(nonce)
        plaintext_sha256 = _sha256(plaintext)
        ciphertext = self._xor_stream(material, nonce, plaintext)
        aad = self._aad(
            key_id=self._key.key_id,
            nonce=nonce_text,
            plaintext_sha256=plaintext_sha256,
            plaintext_size=len(plaintext),
        )
        tag = hmac.new(
            material,
            b"arms-phase5-tag-v1:" + aad + ciphertext,
            hashlib.sha256,
        ).hexdigest()
        return _json_bytes(
            {
                "algorithm": self.algorithm,
                "ciphertext": _b64_encode(ciphertext),
                "format": ENCRYPTED_STAGING_BACKUP_FORMAT,
                "key_id": self._key.key_id,
                "nonce": nonce_text,
                "plaintext_sha256": plaintext_sha256,
                "plaintext_size": len(plaintext),
                "tag": tag,
            },
            maximum=_MAX_ENVELOPE_BYTES,
        )

    def decrypt(self, envelope: bytes) -> bytes:
        try:
            document = _load_json(envelope, maximum=_MAX_ENVELOPE_BYTES)
            required = {
                "algorithm",
                "ciphertext",
                "format",
                "key_id",
                "nonce",
                "plaintext_sha256",
                "plaintext_size",
                "tag",
            }
            if set(document) != required:
                raise ValueError("encrypted envelope fields are invalid")
            if (
                document["format"] != ENCRYPTED_STAGING_BACKUP_FORMAT
                or document["algorithm"] != self.algorithm
            ):
                raise ValueError("encrypted envelope format is unsupported")
            if document["key_id"] != self._key.key_id:
                raise StagingBackupEncryptionError("encrypted backup authentication failed")
            nonce = _b64_decode(document["nonce"], "nonce")
            ciphertext = _b64_decode(document["ciphertext"], "ciphertext")
            if len(nonce) != _NONCE_BYTES:
                raise ValueError("encrypted envelope nonce is invalid")
            plaintext_size = document["plaintext_size"]
            plaintext_sha256 = document["plaintext_sha256"]
            tag = document["tag"]
            if (
                type(plaintext_size) is not int
                or plaintext_size < 1
                or plaintext_size > _MAX_PLAINTEXT_BYTES
                or len(ciphertext) != plaintext_size
                or not isinstance(plaintext_sha256, str)
                or len(plaintext_sha256) != 64
                or not isinstance(tag, str)
                or len(tag) != 64
            ):
                raise ValueError("encrypted envelope metadata is invalid")
            aad = self._aad(
                key_id=document["key_id"],
                nonce=document["nonce"],
                plaintext_sha256=plaintext_sha256,
                plaintext_size=plaintext_size,
            )
            material = self._key._material()
            expected_tag = hmac.new(
                material,
                b"arms-phase5-tag-v1:" + aad + ciphertext,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected_tag, tag):
                raise StagingBackupEncryptionError("encrypted backup authentication failed")
            plaintext = self._xor_stream(material, nonce, ciphertext)
            if not hmac.compare_digest(_sha256(plaintext), plaintext_sha256):
                raise StagingBackupEncryptionError("encrypted backup authentication failed")
            if _json_bytes(document, maximum=_MAX_ENVELOPE_BYTES) != envelope:
                raise ValueError("encrypted envelope must be canonical")
            return plaintext
        except StagingBackupEncryptionError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise StagingBackupEncryptionError("encrypted backup is invalid") from exc


def create_encrypted_staging_backup(
    payload: StagingBackupPayload,
    cipher: StagingBackupCipher,
) -> bytes:
    if not isinstance(payload, StagingBackupPayload):
        raise ValueError("payload must be a StagingBackupPayload")
    if not isinstance(cipher, StagingBackupCipher):
        raise ValueError("cipher must implement StagingBackupCipher")
    if not cipher.local_test_only or cipher.production_encryption_authorized:
        raise StagingBackupEncryptionError("staging backup cipher authority is invalid")
    return cipher.encrypt(serialize_staging_backup_payload(payload))


def open_encrypted_staging_backup(
    envelope: bytes,
    cipher: StagingBackupCipher,
) -> StagingBackupPayload:
    if not isinstance(cipher, StagingBackupCipher):
        raise ValueError("cipher must implement StagingBackupCipher")
    if not cipher.local_test_only or cipher.production_encryption_authorized:
        raise StagingBackupEncryptionError("staging backup cipher authority is invalid")
    plaintext = cipher.decrypt(envelope)
    try:
        return deserialize_staging_backup_payload(plaintext)
    except ValueError as exc:
        raise StagingBackupEncryptionError("decrypted staging backup payload is invalid") from exc
