# RC3F-A1: NinjaTrader session application clock

Baseline: 86658d95d3b6b9a9e92b8307142907fe5d32fc54. Offline source correction
only; no deployment, platform setting change, authority/configuration publication
or execution is authorized by this package.

## Verified clock mismatch

Read-only host inspection on 2026-09-27 found three distinct settings:

* Windows Get-TimeZone: Eastern Standard Time (DST-aware).
* NinjaTrader Config.xml, GeneralOptions/TimeZoneInfoSerializable: UTC.
* Installed CME US Index Futures ETH template version 5119: Central Standard
  Time, Sunday 17:00 to Monday 16:00 and the corresponding weekday sessions.

The baseline bridge used OS DateTime.Now in EvaluatePhysicalTestReadiness
(line 2432), DescribePhysicalTestSessionWindow (2019, plus diagnostic branches
1995/2101), and the initial ResolveNextPhysicalTestSessionWindow call (412).
ResolveNextPhysicalTestSessionWindow and PrintNextSessionSearchDiagnostics then
advanced that OS wall clock via AddDays before GetNextSession. This mixed OS
time with the configured application's session representation.

The deterministic red test froze only the legacy OS-clock seam in a temporary
copy of the extracted production methods. At the same synthetic instant,
2026-09-27 22:30 UTC, OS Eastern was 18:30. Against the ETH window 22:00 UTC to
21:00 UTC the next day, the old readiness method returned MARKET_SESSION_CLOSED.
The corrected production method passes 22:30 and returns PHYSICAL_TEST_READY.
This reproduces the defect offline; it does not assert a new native observation.

## Correction and boundaries

PhysicalTestApplicationNow uses NinjaTrader.Core.Globals.Now, rejecting missing
application timezone metadata. Every bridge session query now originates from
this platform application clock. Session diagnostics capture one application
timestamp for IsInSession, GetNextSession and their next-session searches.
Parameters/local names explicitly say applicationNow. Diagnostic fields identify
application_timezone, trading_hours_timezone, application_now, session_begin,
session_end and is_in_session. Unknown-state logging does not retry a failed
clock or fall back to OS time.

The existing native IsInSession(false, true), GetNextSession(false), search
bounds, TradingHours template, source bars and UTC heartbeat timestamps remain
unchanged. No application timezone is hard-coded. Before-open and at/after-end
cases remain closed; missing/throwing session information stays unknown.

NinjaTrader's documented session-local example uses Core.Globals.Now:
[GetTradingDayBeginLocal](https://docs.ninjatrader.com/ninjascript/gettradingdaybeginlocal).
[IsInSession](https://docs.ninjatrader.com/ninjascript/isinsession) remains the
native membership authority. SDK compilation checks the real API surface;
the behavior harness is explicitly a synthetic SDK, not native session certification.

## Heartbeat IOException: separate read-only investigation

The heartbeat catch logs only the exception type. No matching heartbeat marker
or its stack/HResult was found in the inspected 2026-09-27 log/trace files.
The available IOException trace entries concern shutdown access to an unrelated
Bars cache path; they do not establish the heartbeat exception's cause.

A disposable-file experiment reproduced this mechanism using the actual Python
binary's Path.open('rb') and .NET File.Replace:

* reader held: IOException, HResult -2147024864 (0x80070020, sharing violation);
* reader released: replacement succeeded.

This is a repeatable read/replace contention mechanism consistent with the
current reader/writer pattern, but it does not identify the historical event.
No experiment locked or wrote a live heartbeat file. Snapshot publication,
reader sharing, retries, schema and freshness semantics are unchanged in this
clock package. A separate targeted sharing review is warranted; retain event
stage/HResult evidence before claiming the historical cause.

## Verification and deployment review

New executable regressions cover UTC application/OS Eastern, Eastern/Central/
Tokyo application settings, spring/fall DST dates, before/open/end/after
boundaries, disconnected state, missing template, missing application timezone,
unknown session, consistent next-session queries and explicit diagnostic fields.
The initial red test failed with MARKET_SESSION_CLOSED, then passed unchanged
after the source correction. Existing diagnostic field assertions were updated
to the explicit application/trading-hours labels.

The combined regression run passed 437 cases (one existing Starlette/httpx
deprecation warning). Exact modules, using -B -m pytest -q -p no:cacheprovider
and the existing isolated process-local test profile:

```text
backend/tests/test_sim_native_session_clock_rc3fa1.py
backend/tests/test_sim_native_physical_test_readiness_v2.py
backend/tests/test_sim_native_physical_test_readiness_output_v2.py
backend/tests/test_sim_native_physical_test_session_window_v2.py
backend/tests/test_sim_native_session_window_diagnostics_v2.py
backend/tests/test_sim_native_next_session_search_diagnostic_v2.py
backend/tests/test_sim_native_next_valid_session_resolver_v2.py
backend/tests/test_sim_native_runtime_snapshot_reader_v2.py
backend/tests/test_sim_native_runtime_snapshot_ninjatrader_v2.py
backend/tests/test_sim_native_runtime_snapshot_heartbeat_ninjatrader_v2.py
backend/tests/test_sim_native_admission_runtime_evidence_v3.py
backend/tests/test_first_controlled_trade_preflight_v3.py
backend/tests/test_sim_native_integration_v3.py
backend/tests/test_sim_native_deployment_gate_v3.py
```

All four production sources compiled against the installed NinjaTrader SDK with
zero C# errors, using tools.sim_native_deployment_gate_v3.compile_offline and an
output directory outside bin/Custom. Existing unreachable-code warnings reflect
the compile-time disabled execution branch; no warning suppression was added.

Native submit remains false, auto retry remains false, and the unchanged V3
bootstrap remains observation-only. No CreateOrder/Submit/Cancel/Flatten occurred
in NinjaTrader. DPAPI, signed configuration, commissioning policy, TOPSTEP_150K,
production operation directories, financial state, deployed C# and project were
not changed. The deployed main-source hash is intentionally still the baseline
hash until a separately authorized installation.

Expected after reviewed deployment: a valid connected instant within the native
ETH session becomes PHYSICAL_TEST_READY; closed or unknown sessions still fail
closed. Native confirmation of that expectation is pending deployment review.
