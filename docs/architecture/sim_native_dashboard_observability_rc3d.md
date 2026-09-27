# RC3D SIM_NATIVE dashboard observations

`GET /api/v3/dashboard/sim-native-runtime` is a separate public, no-store read
route, matching existing Dashboard V2 GET conventions. It has no administrative
action, credential, command, activation, reconciliation-permit, DPAPI, or native
account connection. POST is not supported. Readiness is observation only, never
execution eligibility or independent cryptographic certification.

`SimNativeDashboardReaderV3` reads only the two canonical heartbeat files under
`LOCALAPPDATA/ARMS-AI/sim-native-v3/runtime/snapshots`. It checks the exact C#
commissioning schema and existing V2 runtime schema, duplicate keys, bounded
file size, field types, UTC clocks, identity, disabled capability flags, and
path redirection. It does not cache, repair, write, renew configuration, or load
authority secrets. The canonical binding supplies expected public identity.

Freshness uses the existing native `_MAX_EVIDENCE_AGE` authority (15 seconds),
also matching the existing V2 reader limit. Both observations must be fresh;
the returned age is the older heartbeat's age. Future or invalid times fail
closed. The browser ages responses using this server-provided limit and
conservatively includes request elapsed time. Polling cadence is not a separate
freshness authority.

Healthy connected, flat, zero-order observations may be green. Market closure
is `SESSION_CLOSED`, a valid session warning. Stale heartbeats are `STALE`;
missing/unreadable files are `UNAVAILABLE`; malformed identity/schema/safety
claims are `INVALID`. Disconnection and reconciliation fences are prominently
shown. Unknown values remain unknown, never substituted with disabled/flat.
Reported configuration validity is a snapshot claim, not authentication by this
reader. Error text, filesystem paths, and unexpected fields are not returned.

The standalone card and `getSimNativeRuntime()` do not use or change the PAPER
bundle, runtime key, credential, WebSocket, switching, balance, or journal
contracts. No order buttons are present. Existing native submit and retry
constants remain false; no C# or NinjaTrader project/config deployment is involved.
