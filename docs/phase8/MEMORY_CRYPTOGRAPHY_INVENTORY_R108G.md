# R108G MEDAR memory cryptography inventory

Inventory updated: 2026-10-04 (local Windows Python 3.14). The approved packages
are installed only in the ignored project `.venv`; no key or infrastructure was
provisioned.

| Capability | Status | Evidence and Phase 8 decision |
| --- | --- | --- |
| `cryptography` Python package | LOCAL_DEVELOPMENT_AVAILABLE | PyCA `cryptography==50.0.2` is pinned with `cffi==2.1.1` and `pycparser==3.0`. The packages are installed only in the ignored project `.venv`. |
| PyNaCl / `nacl` | NOT_AVAILABLE | Package metadata and module lookup returned absent. |
| PyCryptodome / `Crypto` | NOT_AVAILABLE | Package metadata and module lookup returned absent. |
| OS CurrentUser DPAPI wrapper | AVAILABLE, UNSUPPORTED FOR MEDAR CONTENT | `backend/services/sim_native_authority_v3.py` uses Windows `CryptProtectData`/`CryptUnprotectData` to protect a V3 local authority key. It is not a MEDAR content provider, does not expose the requested AEAD metadata contract, and is not reused to claim production MEDAR encryption. It may inform a future local key-provider seam after separate validation. |
| Phase 5 local ephemeral backup cipher | AVAILABLE, TEST ONLY | `backend/phase5/encrypted_backup.py` explicitly marks its HMAC stream cipher as local-test-only and production encryption unauthorized. It is not a production primitive. Reuse is limited to isolated synthetic tests if needed. |
| Windows CNG standard AEAD | UNKNOWN | No approved repository Python binding for AES-GCM was found. No custom FFI or cipher construction is authorized by this inventory. |
| External KMS / managed key service | NOT_AVAILABLE | No service provisioned or credentials supplied for this task. |
| Existing MEDAR encryption provider | LOCAL_DEVELOPMENT_READY | MEDAR exposes an exact-type AES-256-GCM provider with process-local ephemeral keys. Production readiness remains false. |

The project manifest pins the explicitly approved dependency set. Phase 8 uses
PyCA AES-256-GCM with process-local synthetic keys for encrypted local-development
evidence. No key custody, external KMS, real key material, or production deployment
authority is provided.
