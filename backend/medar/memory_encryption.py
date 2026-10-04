"""Production memory encryption contract; no cryptography is implemented here."""

from typing import Protocol


class MemoryEncryptionProvider(Protocol):
    provider_id: str

    def is_available(self) -> bool: ...
    def encrypt(self, plaintext: bytes, *, tenant_id: str, owner_id: str) -> bytes: ...
    def decrypt(self, ciphertext: bytes, *, tenant_id: str, owner_id: str) -> bytes: ...


class DisabledMemoryEncryption:
    provider_id = "disabled"

    def is_available(self) -> bool:
        return False

    def encrypt(self, plaintext: bytes, *, tenant_id: str, owner_id: str) -> bytes:
        raise PermissionError("production memory encryption is unavailable")

    def decrypt(self, ciphertext: bytes, *, tenant_id: str, owner_id: str) -> bytes:
        raise PermissionError("production memory encryption is unavailable")
