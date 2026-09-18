# Phase 2 authorized PAPER dashboard — V11

Package: `PHASE2_AUTHORIZED_PAPER_DASHBOARD`.
Baseline: `41f568fe3c4648ceeaf8167414d2628dd4a27b86` on
`refactor/backend-architecture`, initially equal to origin with zero ahead/behind
and no tracked/staged changes. All 83 unrelated root text files were fingerprinted
before edits. This package authorizes local PAPER observation and the existing
protected account switch; it does not authorize LIVE execution or product release.

## Recovery audit and verified causes

After the usage interruption, fetch confirmed the same local/remote baseline,
zero ahead/behind, eleven modified tracked V11 files, five new V11 files and an
empty index. The current code, tests and saved regression output were inspected.
The completed direct run was retained: 1,142 passed, one skipped, no failures in
111 modules. The interrupted build had not executed; it was resumed. No reset,
restore, checkout, clean or broad staging command was used. `.env.local` was
left unchanged; its existing API port differed from the isolated test server.

The original browser HTTP wrapper had no administrative credential, and its
WebSocket constructor supplied only a URL while the backend required a header.
New tests first reproduced valid browser credentials being rejected. HTTP
missing/wrong credentials already correctly failed closed. Account changes only
refreshed two cards and old asynchronous requests could republish account A.
The dashboard also submitted fixed demo AI metrics and displayed legacy demo
approval/ranking routes as current state. Empty journal analytics produced NaN;
win-rate fractions were displayed as percentages.

Real Node-to-ASGI transport testing exposed a negotiation requirement missed by
header-only TestClient tests: the browser must receive a selected public
subprotocol. A subsequent full run exposed a disconnect/cancellation cleanup
race (two failures, 5,545 passes, one skip). Child-task cleanup is now shielded
while the original outer cancellation is preserved. A 30-disconnect regression
checks that each connection is removed before the next begins.

## Canonical ownership and authorization

| Boundary | Owner / contract |
| --- | --- |
| Frontend HTTP | `frontend/src/lib/dashboardApi.ts::requestJson` |
| Frontend WebSocket lifecycle | `frontend/src/lib/dashboardConnection.ts::DashboardConnection`; constructor in `dashboardApi.ts::openDashboardWebSocket` |
| Token authority | Existing `backend/security/admin_authorization_v2.py::AdminAuthorizationV2` |
| Protected HTTP | Existing `X-ARMS-ADMIN-TOKEN` header and `require_admin_authorization_v2` |
| Browser transport | `arms-dashboard-v1` plus `arms-admin.<base64url credential>` offered subprotocols |
| Negotiated protocol | Only `arms-dashboard-v1`; credential is never selected/echoed |
| Native WebSocket clients | Existing canonical admin header remains supported |
| Runtime/account | Existing coordinator and published runtime generation |
| Financial/risk projection | Existing dashboard engine, account state, portfolio and journal owners |
| Market/candidate | Observational `/market/latest-analysis`, backed by V10 canonical pipeline stores |

The transport adapter validates the same admin credential before acceptance.
Missing, wrong, malformed and ambiguous credentials fail closed; a wrong supplied
header cannot be rescued by a valid protocol credential. The hub accepts a public
protocol name and removes disconnected clients. No new token issuer, session
database, broker authority or dependency was added. HTTP redirects are rejected
and browser cookies are omitted. Public GETs receive no unnecessary credential.

The local configuration boundary is an operator-entered PAPER admin credential
in a password field. It remains in page memory and is cleared on disconnect,
unmount or reload. Public build configuration contains only API origin and
symbol/timeframe selection. No server secret is injected into a bundle, no token
is placed in a URL or browser storage, and no LIVE credentials are used.
See [frontend setup](../../frontend/README.md). Base64 is encoding, not encryption;
loopback HTTP/WS is supported locally, remote origins require HTTPS/WSS and a
separately configured deployment boundary. Credential-bearing handshake/header
logging must be redacted if a proxy is introduced.

## Projection, isolation and observational boundary

The existing live HTTP and WebSocket snapshot share a projection adapter. For a
coordinated runtime it adds that fixed account identity/generation, actual
execution mode, canonical open positions and serialized journal entries. Legacy
uncoordinated/fake-service compositions retain their existing snapshot shape.
It never looks up a replacement account while serializing a retired runtime.

The frontend reads the account context before and after its parallel GET bundle
and requires the snapshot identity to match. A connection epoch and request
sequence reject delayed completions. Every switch/disconnect clears all cards;
old socket events cannot repopulate them. Backend retirement still closes old
sockets with 1012, and the frontend reconnects. Failed/unavailable runtimes expose
no retained financial or candidate state. Ambiguous authentication/network
closures require explicit reconnect instead of repeated credential retries.

The account selector uses operational identities from the backend catalog, not a
fixed list of profile names. Balance/equity, realized/unrealized PnL, risk blocks,
positions, execution status, journal and existing session analytics are backend
projections. Journal cards use canonical portfolio settled PnL, canonical wins
and losses and the backend's percentage field. The frontend performs no risk,
sizing, PnL or percentage calculation. PAPER labels replace misleading LIVE labels.

V10 analysis/candidates, provenance, market availability and unavailable states
are visible through the existing data-panel presentation. Candidate approval is
clearly observational and still requires independent canonical admission.
Legacy demo setup/approval/simulation/ranking/fusion endpoints and components
remain available for compatibility, but are not requested/rendered as authoritative
PAPER state. Read, refresh, subscription and five-second polling cannot trade.
The only dashboard command is the existing protected account switch.

## Verification evidence

- Frontend: `npm run lint`; `node --test src/lib/dashboardApi.test.mjs
  src/lib/dashboardConnection.test.mjs src/lib/dashboardProjection.test.mjs`;
  `npm run build` (includes TypeScript). All 23 Node tests pass. No invented npm
  test/typecheck script. Build uses an explicit temporary test API origin without
  modifying local environment files.
- Backend direct: 111 modules selected by the recorded module-name predicate in
  the V9 inventory, 1,142 passed / 0 failed / 1 skipped before cleanup repair.
  Subsequent focused cleanup/retirement checks: 37 passed. Final V11 module:
  15 passed, including 30 repeated disconnects in one test.
- `test_authorized_dashboard_v11.py` checks HTTP valid/missing/wrong credentials,
  WebSocket valid/missing/wrong/malformed credentials, no credential echo,
  financial projection, account retirement, real candidate observation and
  execution-mutator tripwires. A real loopback uvicorn server runs the actual
  transpiled frontend TypeScript client with Node native fetch/WebSocket; no
  fetch/socket mocks are used in that integration. It reads a V10-generated
  candidate and a closed PAPER trade, switches A→B, checks 1012 retirement and
  verifies that A's candidate and journal are absent from B.
- Browser: production Next app and isolated PAPER backend on loopback, no real
  credentials or accounts. Missing/wrong credentials show fail-closed errors.
  Valid auth displays CONNECTED. Account A shows balance/equity 150020, one closed
  trade, realized PnL 20 and win rate 100%; B shows balance/equity 50000, empty
  history, PnL 0 and win rate 0%. A→B increments generation, clears A's history,
  and reconnects. Disconnect clears all projections. Missing market analysis is
  explicitly unavailable; no legacy fake approval cards are shown.
- Phase 1 route source evidence was updated for the reviewed adapter calls; no
  classification, authorization requirement or execution invariant was weakened.

Final full-backend and staged-certification results are recorded in the V9
capability inventory's `v11_test_execution` section after those gates complete.

## Remaining scope

V11 closes MVP-018, MVP-019 and MVP-021 for the documented local PAPER boundary.
The mandatory inventory is 21/24 (87%, integer floor), with P0=0, P1=2, P2=1;
six post-MVP groups remain excluded. Phase 1 stays CLOSED. Remaining mandatory
work is certified input maintenance (MVP-010), the joined operator startup /
public-input / browser / restart scenario (MVP-023), and remaining research
validation provenance (MVP-024). Browser verification here is an isolated test
environment, not a sustained feed or deployment certificate.

Next: `PHASE2_PAPER_MVP_OPERATIONAL_ACCEPTANCE`. `LIVE_EXECUTION=NO`.
