# R108G MEDAR memory cryptography inventory

Inventory date: 2026-10-03 (local Windows Python 3.14.6). Read-only inspection; no package, key, or infrastructure was installed or provisioned.

| Capability | Status | Evidence and Phase 8 decision |
| --- | --- | --- |
| `cryptography` Python package | NOT_AVAILABLE | Package metadata and module lookup returned absent. No AES-GCM or ChaCha20-Poly1305 Python provider is available from it. |
| PyNaCl / `nacl` | NOT_AVAILABLE | Package metadata and module lookup returned absent. |
| PyCryptodome / `Crypto` | NOT_AVAILABLE | Package metadata and module lookup returned absent. |
| OS CurrentUser DPAPI wrapper | AVAILABLE, UNSUPPORTED FOR MEDAR CONTENT | `backend/services/sim_native_authority_v3.py` uses Windows `CryptProtectData`/`CryptUnprotectData` to protect a V3 local authority key. It is not a MEDAR content provider, does not expose the requested AEAD metadata contract, and is not reused to claim production MEDAR encryption. It may inform a future local key-provider seam after separate validation. |
| Phase 5 local ephemeral backup cipher | AVAILABLE, TEST ONLY | `backend/phase5/encrypted_backup.py` explicitly marks its HMAC stream cipher as local-test-only and production encryption unauthorized. It is not a production primitive. Reuse is limited to isolated synthetic tests if needed. |
| Windows CNG standard AEAD | UNKNOWN | No approved repository Python binding for AES-GCM was found. No custom FFI or cipher construction is authorized by this inventory. |
| External KMS / managed key service | NOT_AVAILABLE | No service provisioned or credentials supplied for this task. |
| Existing MEDAR encryption provider | DISABLED | `backend/medar/memory_encryption.py` contains a fail-closed disabled provider only. |

`requirements.txt` and `backend/requirements.txt` contain no approved cryptography dependency. Production MEDAR sensitive-memory encryption remains **BLOCKED**. R108H may add a provider-neutral contract and local-test implementation. R108I must not claim production AEAD validation without an approved installed implementation.
