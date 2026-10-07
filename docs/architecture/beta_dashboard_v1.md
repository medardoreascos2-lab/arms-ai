# ARMS AI Beta Dashboard V1

## Status and boundary

Beta Dashboard V1 adapts the existing `/dashboard-v2` route. It does not create a
second frontend application or connect a browser to NinjaTrader. Beta product
data flows only through existing backend read stores and the canonical PAPER
dashboard/journal projection:

```text
ARMS PAPER runtime -> existing read stores -> authenticated beta API -> dashboard
```

The beta API exposes no order, execution, account-switch, PAPER-enable,
LIVE-enable, risk-parameter, strategy-parameter, or NinjaTrader route. Existing
owner operations remain inside the admin-only owner console and retain their
pre-existing independent administrative credential checks.

## Existing frontend reuse map

`REUSE_AS_IS=` the Next.js application, `/dashboard-v2` route, global visual
language, responsive cards/tables, canonical dashboard read service, PAPER
journal, live signal/analysis stores, and the existing advanced owner console.

`REUSE_WITH_CHANGES=` `/dashboard-v2` now enters through beta identity and shows
role-specific navigation; existing read data is projected into the public
versioned signal contract; delivery uses authenticated five-second polling.

`ADMIN_ONLY=` account selection, runtime health, internal system/risk state,
technical diagnostics, advanced intelligence, and all existing operational
cards in the owner console.

`HIDDEN_FROM_BETA=` internal thresholds, raw traces, account identities,
runtime namespaces, proprietary reasoning, strategy internals, execution
approval/simulation details, and administrative credentials.

`MISSING=` payment integration, public deployment hardening, email/password
reset delivery, multi-process session coordination, and beta WebSocket/SSE.
Those are intentionally outside Beta V1. Polling is retained because the
existing WebSocket is bound to the owner admin credential and operational
snapshot.

## User and session model

The isolated SQLite store records `user_id`, email identity, role, status,
`beta_start_at`, `beta_expires_at`, `created_at`, and `last_login_at`. Roles are
`admin`, `beta_user`, and `disabled`; status is independently fail-closed.
Beta access defaults to 30 days. Disabled, not-started, expired, malformed, or
incomplete beta access is rejected on login and on every authenticated request.

Passwords use salted PBKDF2-HMAC-SHA256 with 600,000 iterations. The browser
receives an opaque HttpOnly SameSite=Strict session cookie, never a password
hash or server secret. Server-side sessions store only SHA-256 token digests.
Admin mutations require both the admin role and a per-session CSRF token.

## Local configuration

Provide an isolated beta database path and a bootstrap admin through process
environment or a local secret manager before starting the existing API:

```text
ARMS_BETA_DATABASE_PATH=C:\Development\ARMS-AI\data\beta\dashboard_v1.sqlite3
ARMS_BETA_ADMIN_EMAIL=<local admin email>
ARMS_BETA_ADMIN_PASSWORD=<local secret of at least 12 characters>
ARMS_BETA_COOKIE_SECURE=false
ARMS_BETA_SYMBOL=MNQ
ARMS_BETA_TIMEFRAME=5m
```

`ARMS_BETA_COOKIE_SECURE=false` is for loopback HTTP review only. Any non-local
HTTPS deployment must set it to `true`. Never put the admin password in source,
`.env` committed to Git, a `NEXT_PUBLIC_*` variable, a URL, or documentation.
When no database path is configured the store is in-memory and all beta access
is lost on restart, which is the fail-closed development default.

The existing frontend still needs only the public API origin:

```text
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Open `http://127.0.0.1:3000/dashboard-v2`. Admins can create, disable, enable,
and extend beta users. Beta users can access only LIVE, HISTORY, and PERFORMANCE.

## Signal and delivery contract

Contract `1.0` contains the requested signal identity/timestamps, instrument,
contract, direction, status, plan prices, reward/risk, confidence, confluence,
PAPER-only marker, hashed source runtime identity, safe decision summary,
result, exit, and PAPER P&L fields. Rejected signals never expose plan prices.
The frontend rejects non-PAPER contracts, ignores stale/duplicate snapshots,
and prevents an older signal from replacing a newer last-known signal.

Performance is calculated only from available canonical closed PAPER journal
records. Missing or unreliable values remain `null` and render as unavailable;
the beta projection does not manufacture profit factor, drawdown, or P&L.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q backend\tests\test_beta_dashboard_v1.py
cd frontend
node --test src/lib/betaDashboardApi.test.mjs src/lib/betaDashboardProjection.test.mjs src/components/dashboard-v2/BetaDashboardV1.test.mjs
npm.cmd run lint
npm.cmd run build
```
