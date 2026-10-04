"""Versioned MEDAR memory envelope with scope-bound authenticated metadata.

This format does not itself grant read/write authority. The current concrete
provider is synthetic local-test-only and cannot seal sensitive records.
"""

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass, field

from backend.medar.durable_memory_encryption import (
    AESGCMEphemeralMemoryEncryption, DurableMemoryEncryptionProvider,
    EncryptedMemoryPayload, EphemeralTestMemoryEncryption,
)
from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableSensitivity,
    MemoryLifecycle, content_digest,
)


_SCHEMA_VERSION = 1
_MAX_ENVELOPE_BYTES = 128 * 1024


def _metadata_bytes(memory_id: str, owner_id: str, tenant_id: str, domain: DurableMemoryDomain, sensitivity: DurableSensitivity, version: int) -> bytes:
    return json.dumps({
        "schema_version": _SCHEMA_VERSION,
        "memory_id": memory_id,
        "owner_id": owner_id,
        "tenant_id": tenant_id,
        "domain": domain.value,
        "sensitivity": sensitivity.value,
        "version": version,
    }, sort_keys=True, separators=(",", ":")).encode("ascii")


@dataclass(frozen=True)
class EncryptedMemoryEnvelope:
    memory_id: str
    owner_id: str
    tenant_id: str
    domain: DurableMemoryDomain
    sensitivity: DurableSensitivity
    version: int
    payload: EncryptedMemoryPayload = field(repr=False)
    content_hash: str | None = None
    schema_version: int = _SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("memory_id", "owner_id", "tenant_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.domain, DurableMemoryDomain) or not isinstance(self.sensitivity, DurableSensitivity):
            raise TypeError("memory classification must be typed")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("memory version must be positive")
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION or not isinstance(self.payload, EncryptedMemoryPayload):
            raise ValueError("unsupported encrypted memory envelope")
        if self.sensitivity in (DurableSensitivity.PERSONAL, DurableSensitivity.SENSITIVE, DurableSensitivity.HIGHLY_SENSITIVE):
            if self.content_hash is not None:
                raise ValueError("sensitive memory must not expose plaintext content hash")
        elif self.content_hash is not None and (
            not isinstance(self.content_hash, str) or len(self.content_hash) != 64
            or any(character not in "0123456789abcdef" for character in self.content_hash)
        ):
            raise ValueError("content hash must be lowercase SHA-256")

    def associated_data(self) -> bytes:
        return _metadata_bytes(self.memory_id, self.owner_id, self.tenant_id, self.domain, self.sensitivity, self.version)

    def to_bytes(self) -> bytes:
        document = {
            "schema_version": self.schema_version,
            "memory_id": self.memory_id,
            "owner_id": self.owner_id,
            "tenant_id": self.tenant_id,
            "domain": self.domain.value,
            "sensitivity": self.sensitivity.value,
            "version": self.version,
            "content_hash": self.content_hash,
            "ciphertext": base64.b64encode(self.payload.ciphertext).decode("ascii"),
            "algorithm": self.payload.algorithm_identifier,
            "key_reference": self.payload.key_reference,
            "key_version": self.payload.key_version,
            "nonce_metadata": self.payload.nonce_metadata,
            "associated_data_hash": self.payload.associated_data_hash,
            "authenticated": self.payload.authenticated,
            "local_test_only": self.payload.local_test_only,
        }
        encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("ascii")
        if len(encoded) > _MAX_ENVELOPE_BYTES:
            raise ValueError("encrypted memory envelope is too large")
        return encoded

    @classmethod
    def from_bytes(cls, encoded: bytes) -> "EncryptedMemoryEnvelope":
        if not isinstance(encoded, bytes) or not encoded or len(encoded) > _MAX_ENVELOPE_BYTES:
            raise ValueError("encrypted memory envelope is invalid")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate encrypted memory field")
                result[key] = value
            return result
        try:
            document = json.loads(encoded.decode("ascii"), object_pairs_hook=unique)
            expected = {
                "schema_version", "memory_id", "owner_id", "tenant_id", "domain", "sensitivity",
                "version", "content_hash", "ciphertext", "algorithm", "key_reference", "key_version",
                "nonce_metadata", "associated_data_hash", "authenticated", "local_test_only",
            }
            if not isinstance(document, dict) or set(document) != expected:
                raise ValueError("encrypted memory envelope fields are invalid")
            ciphertext = base64.b64decode(document["ciphertext"], validate=True)
            if base64.b64encode(ciphertext).decode("ascii") != document["ciphertext"]:
                raise ValueError("noncanonical encrypted content")
            payload = EncryptedMemoryPayload(
                ciphertext, document["algorithm"], document["key_reference"],
                document["key_version"], document["nonce_metadata"],
                document["associated_data_hash"], document["authenticated"],
                document["local_test_only"],
            )
            envelope = cls(
                document["memory_id"], document["owner_id"], document["tenant_id"],
                DurableMemoryDomain(document["domain"]), DurableSensitivity(document["sensitivity"]),
                document["version"], payload, document["content_hash"], document["schema_version"],
            )
            if envelope.to_bytes() != encoded:
                raise ValueError("encrypted memory envelope must be canonical")
            return envelope
        except (UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, binascii.Error) as exc:
            raise ValueError("encrypted memory envelope is invalid") from exc


def seal_memory_content(record: DurableMemoryRecord, provider: DurableMemoryEncryptionProvider) -> EncryptedMemoryEnvelope:
    if not isinstance(record, DurableMemoryRecord) or record.status is not MemoryLifecycle.ACTIVE:
        raise ValueError("active durable memory record is required")
    sensitive = record.sensitivity in (
        DurableSensitivity.PERSONAL, DurableSensitivity.SENSITIVE,
        DurableSensitivity.HIGHLY_SENSITIVE,
    )
    if type(provider) is AESGCMEphemeralMemoryEncryption:
        if provider.production_ready or not provider.local_test_only or not provider.sensitive_local_development_ready:
            raise PermissionError("AES-GCM development provider classification is invalid")
    elif type(provider) is EphemeralTestMemoryEncryption:
        if sensitive:
            raise PermissionError("legacy test cipher cannot seal sensitive memory")
        if provider.production_ready or not provider.local_test_only:
            raise PermissionError("legacy test provider classification is invalid")
    else:
        raise PermissionError("approved memory encryption provider is required")
    if record.source_type != "synthetic_test":
        raise PermissionError("local encrypted envelope requires a synthetic record")
    metadata = _metadata_bytes(record.memory_id, record.owner_id, record.tenant_id, record.domain, record.sensitivity, record.version)
    payload = provider.encrypt(record.content.encode("utf-8"), associated_data=metadata)
    if not payload.authenticated or not payload.local_test_only:
        raise PermissionError("local provider returned unapproved payload")
    return EncryptedMemoryEnvelope(
        record.memory_id, record.owner_id, record.tenant_id, record.domain,
        record.sensitivity, record.version, payload,
        None if sensitive else record.content_hash,
    )


def open_memory_content(
    envelope: EncryptedMemoryEnvelope,
    provider: DurableMemoryEncryptionProvider,
    *,
    memory_id: str,
    owner_id: str,
    tenant_id: str,
    domain: DurableMemoryDomain,
    sensitivity: DurableSensitivity,
    version: int,
) -> str:
    if not isinstance(envelope, EncryptedMemoryEnvelope) or (
        envelope.memory_id != memory_id or envelope.owner_id != owner_id
        or envelope.tenant_id != tenant_id or envelope.domain is not domain
        or envelope.sensitivity is not sensitivity or envelope.version != version
    ):
        raise PermissionError("encrypted memory scope mismatch")
    sensitive = envelope.sensitivity in (
        DurableSensitivity.PERSONAL, DurableSensitivity.SENSITIVE,
        DurableSensitivity.HIGHLY_SENSITIVE,
    )
    if sensitive:
        if type(provider) is not AESGCMEphemeralMemoryEncryption or provider.production_ready or not provider.sensitive_local_development_ready:
            raise PermissionError("sensitive local decryption requires the AES-GCM development provider")
    elif type(provider) not in (EphemeralTestMemoryEncryption, AESGCMEphemeralMemoryEncryption) or provider.production_ready:
        raise PermissionError("approved local encryption provider is required")
    plaintext = provider.decrypt(envelope.payload, associated_data=envelope.associated_data())
    try:
        content = plaintext.decode("utf-8")
        if envelope.content_hash is not None and content_digest(content) != envelope.content_hash:
            raise ValueError("encrypted memory content hash mismatch")
        return content
    except (UnicodeError, ValueError) as exc:
        raise PermissionError("encrypted memory content invalid") from exc
