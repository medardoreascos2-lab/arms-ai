"""Ephemeral MEDAR key-version lifecycle and rotation contract.

Registry state is process-local. Production key custody is not implemented.
"""

from dataclasses import dataclass
from enum import Enum

from backend.medar.durable_memory_encryption import EphemeralTestMemoryEncryption
from backend.medar.durable_memory_record import DurableMemoryRecord
from backend.medar.encrypted_memory_envelope import (
    EncryptedMemoryEnvelope, open_memory_content, seal_memory_content,
)


class MemoryKeyState(str, Enum):
    ACTIVE = "ACTIVE"
    DECRYPT_ONLY = "DECRYPT_ONLY"
    RETIRED = "RETIRED"
    REVOKED = "REVOKED"


@dataclass(frozen=True)
class MemoryKeyVersionMetadata:
    key_reference: str
    key_version: str
    algorithm_identifier: str
    state: MemoryKeyState
    local_test_only: bool = True

    def __post_init__(self) -> None:
        if not self.local_test_only:
            raise ValueError("production key custody is not implemented")


class EphemeralMemoryKeyRegistry:
    def __init__(self):
        self._entries: dict[str, tuple[EphemeralTestMemoryEncryption, MemoryKeyState]] = {}

    def register(self, provider: EphemeralTestMemoryEncryption, *, state: MemoryKeyState = MemoryKeyState.ACTIVE) -> None:
        if type(provider) is not EphemeralTestMemoryEncryption or provider.production_ready:
            raise PermissionError("only exact ephemeral test provider may be registered")
        if not isinstance(state, MemoryKeyState) or state in (MemoryKeyState.RETIRED, MemoryKeyState.REVOKED):
            raise ValueError("new key must be active or decrypt-only")
        if provider.key_version in self._entries:
            raise ValueError("key version already registered")
        if any(existing.key_reference == provider.key_reference for existing, _ in self._entries.values()):
            raise ValueError("key reference already registered")
        if state is MemoryKeyState.ACTIVE and any(current is MemoryKeyState.ACTIVE for _, current in self._entries.values()):
            raise ValueError("only one active key version is allowed")
        self._entries[provider.key_version] = (provider, state)

    def transition(self, key_version: str, new_state: MemoryKeyState) -> None:
        entry = self._entries.get(key_version)
        if entry is None or not isinstance(new_state, MemoryKeyState):
            raise ValueError("known key version and state required")
        provider, old_state = entry
        allowed = {
            MemoryKeyState.ACTIVE: {MemoryKeyState.DECRYPT_ONLY, MemoryKeyState.REVOKED},
            MemoryKeyState.DECRYPT_ONLY: {MemoryKeyState.RETIRED, MemoryKeyState.REVOKED},
            MemoryKeyState.RETIRED: {MemoryKeyState.REVOKED},
            MemoryKeyState.REVOKED: set(),
        }
        if new_state not in allowed[old_state]:
            raise PermissionError("key-state transition is not allowed")
        self._entries[key_version] = (provider, new_state)
        if new_state in (MemoryKeyState.RETIRED, MemoryKeyState.REVOKED):
            provider.close()

    def metadata(self) -> tuple[MemoryKeyVersionMetadata, ...]:
        return tuple(
            MemoryKeyVersionMetadata(provider.key_reference, provider.key_version, provider.algorithm_identifier, state)
            for provider, state in sorted(self._entries.values(), key=lambda item: item[0].key_version)
        )

    def encrypt(self, record: DurableMemoryRecord) -> EncryptedMemoryEnvelope:
        active = [provider for provider, state in self._entries.values() if state is MemoryKeyState.ACTIVE]
        if len(active) != 1:
            raise PermissionError("active memory key is unavailable")
        return seal_memory_content(record, active[0])

    def decrypt(self, envelope: EncryptedMemoryEnvelope) -> str:
        if not isinstance(envelope, EncryptedMemoryEnvelope):
            raise TypeError("encrypted memory envelope is required")
        entry = self._entries.get(envelope.payload.key_version)
        if entry is None:
            raise PermissionError("memory key version is unavailable")
        provider, state = entry
        if state not in (MemoryKeyState.ACTIVE, MemoryKeyState.DECRYPT_ONLY):
            raise PermissionError("memory key version cannot decrypt")
        if envelope.payload.key_reference != provider.key_reference:
            raise PermissionError("memory key reference mismatch")
        return open_memory_content(
            envelope, provider, memory_id=envelope.memory_id,
            owner_id=envelope.owner_id, tenant_id=envelope.tenant_id,
            domain=envelope.domain, sensitivity=envelope.sensitivity,
            version=envelope.version,
        )

    def close(self) -> None:
        for provider, _ in self._entries.values():
            provider.close()

    def __enter__(self) -> "EphemeralMemoryKeyRegistry":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
