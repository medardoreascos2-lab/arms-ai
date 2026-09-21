# Sprint 15Y-R1 startup compatibility and health-first activation

Baseline: `661b3aeae48b6b88eb960d036ecaa46940bded8f`, branch
`refactor/backend-architecture`. This repair is analysis-only. No native
activation, real activation allowance, account access, commit or push occurred.
The runtime validation below was bounded, unarmed, and shut down afterward.

## Verified causes

The installed NinjaScript contains the exact reviewed authored implementation,
followed by NinjaTrader-generated Indicator, MarketAnalyzerColumn and Strategy
wrappers. The previous whole-file comparison incorrectly rejected this form.
The previous constructor also started its 900 nominal QPC-second activation
allowance before HTTP/frontend/adapter health checks were possible.

The listener on port 8001 was PID 37532 running the Sprint 15R
`.arms-dev/sprint15r/dashboard_host.py`, not the analysis-only application.
Its analysis route returned 404. The listener on port 3000 was an old Next
process, PID 67632, started before the reviewed frontend build. Its analysis
route returned 404 even though the route exists in that build. A fresh process
on temporary port 13002 served the SAME build ID `69D6Mk4RqyrMotwKCRllK` and
returned HTTP 200 for `/market-analysis`. This distinguishes stale running
routing state from a missing source route/build artifact. No old service was
stopped or reconfigured. The temporary comparison process was stopped.

## Exact exporter fingerprint contract

1. Strict UTF-8 decode with optional leading BOM; normalize CRLF to LF. Reject
   residual CR and NUL. This is source compatibility, not compiled-assembly
   attestation or proof of a running chart's configuration.
2. Recognize at most one complete literal line:
   `#region NinjaScript generated code. Neither change nor remove.`
   A matching region must begin after LF and be followed by LF. No marker is
   permitted only when the entire file matches the authored fingerprint.
3. SHA256 the UTF-8 authored prefix, removing only trailing LF separator lines.
   All other bytes, including comments, spaces, code and directives, remain in
   the fingerprint. Expected digest:
   `593d84014549759d8ad451ebedfd1fa87392aab9df97021ad592cda8f42f9a50`.
   This scope derives from the unchanged reviewed C# source, whose original
   full normalized file digest remains
   `9383d39f8b39f62d5bed235d69f4200e0a31d5a14515e5caf078805d03fcd350`.
4. A tail must have exactly one terminal `#endregion`, with only LF afterward.
   Tokenize its body using identifiers, decimal integer tokens, `==`, `!=`,
   `++`, and otherwise individual non-whitespace characters. Join tokens with
   LF and require SHA256
   `602e415d3580d6835424b667cbec475d7a80987cde07ff282686144d58fa45f1`.
   The checked-in fixture is the actual observed generated tail. This is a
   closed token allowlist for that wrapper structure, not a blanket exemption
   for text labeled generated. Only whitespace/line-ending formatting variation
   is accepted. Comments, directives, new statements, changed expressions,
   extra classes, split tokens, missing/duplicate boundaries and truncation
   fail closed. Other NinjaTrader wrapper versions require separate review.

The installed source passed this contract. The compiled Sprint 15W exporter
remains source-compatible and does not need recompilation for this Python-only
repair; prior operator-confirmed compilation is still the deployment premise.
No C# or canonical market/sidecar behavior changed.

## Health-first contract

The supported launcher now performs this ordered sequence:

1. Verify source compatibility, dependencies and unused local ports. Allocate a
   fresh UUID and exclusive runtime directory/claim with PID and process creation
   FILETIME. Never attach to another service merely because its port responds.
2. Start one loopback-only analysis backend with no adapter. Verify its HTTP
   health response, run UUID, PID, creation identity, listener owner and worker.
3. Copy the reviewed frontend source/config into the fresh runtime. Include its
   `dashboard-v2` imports. Exclude `.env`, prior builds, runtime state and native
   evidence. Use a dependency junction only in the build tree. Build a separate
   production artifact using the explicit backend URL in the child environment.
   Existing builds, services and frontend configuration stay untouched.
4. Start an owned loopback frontend. Match its listener PID/creation identity,
   fresh build ID, HTTP 200 analysis page, expected page markers, actual script
   asset availability and compiled API origin.
5. Exclusively create an empty inbox and construct the fresh adapter. Its state
   is WAITING with `activation_start=None`. Construction fixes the reader QPC
   fence, but does not start the allowance. Input before arming revokes it.
6. Independently read three health samples across separate intervals. Verify
   run/process identity, WAITING, advancing BACKGROUND worker and adapter
   heartbeats, no session/input, no allowance, and recent QPC samples. Health
   GET does not increment counters or arm anything.
7. Recheck both listeners, dashboard HTTP status, empty input, live processes
   and the recent waiting evidence. Only the explicitly authorized normal
   launcher mode now calls the in-process one-shot `arm_activation()` method.
   The unchanged 900-second allowance is measured from this final gate's QPC,
   not from construction. Reentry, reset, stale evidence and auto-recovery are
   rejected. No POST/arm/control/order/account endpoint is exposed.

`--validate-offline` follows all health gates but NEVER calls arm_activation.
It records OFFLINE_VALIDATED_UNARMED and then revokes/closes the adapter and
stops its owned backend/frontend. All failure paths latch FAILED and clean up;
no saved WAITING/status file grants authority. Claims/results are audit records
only: readiness must come from fresh live HTTP/process/counter checks. A failed
build in the initial local validation was correctly rejected before any adapter
or allowance; the copy was fixed to include the committed dashboard-v2 import.

The low-level adapter's `health_gated=False` compatibility option is used only
by existing deterministic history/transport tests. The operational launcher
never uses it; default construction is unarmed. It is not a certified startup
entry point. Existing transport/processing/pair budgets and absolute timestamp
tolerances are unchanged. Clock inventory changes list only new health-clock
calls and changed line locations; prior time-authority assessments are preserved.

## Validation and retained limits

The bounded validation run used UUID
`64b6120f-c56a-4f7f-b055-0c3603772662`. Its fresh production frontend returned
HTTP 200, including its page scripts and the correct compiled loopback API URL.
Adapter counters advanced 7, 14, 21; background counters 114, 121, 128. Input
was empty; activation start was null in all samples and on shutdown. Both owned
processes stopped. Exact run artifacts remain under `.arms-dev/sprint15y-r1/`.
The detailed test counts, command list, source hashes and preservation results
are recorded in `backend/tests/analysis_startup_sprint15yr1.json`.

The future default dashboard URL is `http://127.0.0.1:13001/market-analysis`;
it is NOT running after offline validation. Future startup creates a different
UUID/inbox and verifies this URL again. Ports must be free; the launcher will
not replace a conflicting service. No native activation or fresh market
observation was performed. Absolute market recency/session authority remain
UNKNOWN and news UNCERTIFIED. PAPER/SIM remain disabled and LIVE authority NO.
The human still sets Provider31 / NQ DEC26 / Minute 1 / CME US Index Futures ETH /
UTC and activates the unchanged indicator only after a future authorized gate.

## Proposed commit scope

- backend/market_data/exporter_identity_v1.py
- backend/market_data/analysis_startup_v1.py
- backend/market_data/fresh_native_adapter_v1.py
- backend/api/market_analysis_time_app_v1.py
- tools/analysis_native_startup_v1.py
- tools/start_analysis_native_v1.py
- backend/tests/fixtures/ArmsReadOnlyMarketV1.generated.txt
- backend/tests/test_analysis_startup_sprint15yr1.py
- backend/tests/test_fresh_native_adapter_sprint15y.py
- backend/tests/test_analysis_time_sprint15x.py
- backend/tests/clock_preflight_sprint15t.json
- backend/tests/analysis_startup_sprint15yr1.json
- docs/architecture/analysis_startup_sprint15yr1.md

Next step: review and explicitly authorize this local commit, then separately
request the health-first adapter start. No real allowance was started here.
