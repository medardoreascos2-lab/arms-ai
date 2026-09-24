# R5.3-H — configured NinjaScript diagnostic host

## Status and authority

Implemented for offline SDK compilation and synthetic integration tests.
Not installed or activated by this package. No trading or historical admission.
Native behavior, source timestamp meaning and the R2/R4 false-return cause remain
unresolved. A successful test run is not a native capture.

## Composition

`NinjaTrader.NinjaScript.Indicators.ArmsSessionTimestampInterpretationProbeV1`
composes the unchanged Plan, Executor, Lifecycle, Evidence, NativeBridge,
NativeContext and ContextEnvelope helpers in `Arms.AI.Diagnostics.R53`.
All eight C# authored files must eventually compile in the same NinjaScript
assembly. This package does not copy any files into a NinjaTrader installation
and does not produce or import hand-written NinjaScript generated wrappers.

## Operator interface

Five properties only, under `ARMS diagnostic only`:

- ProbeEnabled: false.
- OutputDirectory: empty string.
- MarketReopenConfirmed: false.
- NqDataFlowConfirmed: false.
- ConnectionStableConfirmed: false.

These are operator confirmations, not independent market/connection observations.
They grant only this bounded diagnostic attempt, never order or account access.

## State management

SetDefaults updates UI values only. It does not create requests or writers.
Configure records eligibility, without reading market data or opening files.
DataLoaded consumes one initialization opportunity for the instance. If enabled,
configured and not terminated, it creates one owner-bound attempt; otherwise it
performs no request or evidence operation. Turning on an already-consumed disabled
instance via repeated state calls cannot rearm it. OnBarUpdate does nothing.

The configured chart must still identify NQ DEC26, Minute/1, Last and the expected
TradingHours name/zone whenever operator settings are checked. Chart Bars identity
must stay unchanged. The host does not read ChartControl, use a UI dispatcher or
change connections. F independently checks the full requested/returned calendar,
request policies, local calendar dates and the fingerprinted Bars snapshot.

Terminated calls only the attempt owned by this exact indicator. A shallow copy
of a running indicator cannot operate on or close that owner's attempt. The
normal separate-instance property-copy model works with independent resources;
a second instance aimed at an occupied capture directory fails before making
another request. One shared-directory failure does not invalidate the owner.

Repeated states and late callbacks cannot create another request or result.
Only the request wrapper forwards callbacks to C, retaining the actual sender.
An observer calls completion inspection after callback delivery returns and after
Start returns. For an inline callback this defers publication until Submit has
returned and C has finished preparation/closure. Async callbacks take the same
path after C completes. No timer, task, thread creation or retry belongs to the
native host; test threads exist only in the explicit synthetic harness.

## Publication and cleanup

C owns the request and writer after factory transfer. E owns the underlying SDK
request and rejects clone disposal. Cancellation is cooperative: an in-flight
operation can finish, but C waits before disposing its resources and cannot mark
a cancelled attempt ready. The host never directly calls a native constructor or
GetNextSession; A/B/E retain the 12-attempt and 11-constructor budgets.

The host attempts G.PublishSeal at most once, only after C.ReadyForSeal. G checks
current environment, files and cached context; it does not read a disposed Bars
request. An error before or during publication leaves no accepted full envelope.
An already-present inner matrix seal is not a completed native envelope.

Host completion inspection is serialized. Cooperative stops and observation
checkpoints are tested, but there is no claim that an OS file rename can be
recalled after publication, or that arbitrary concurrent external file changes
are universally eliminated. User reconfiguration or termination after a valid
seal does not retroactively revoke or rewrite the sealed observation.

A single bounded NinjaScript Output notification provides status, fixed/safe
failure identifiers and exception category; context operation/index are included
when available. Provider messages, paths and stacks are not logged. Notification
failure is swallowed without retrying requests or changing the evidence. Failed
or pending attempts are not promoted merely because a notification was printed.
A missing callback remains pending until explicit operator termination; no
automatic timeout, reconnect or retry is introduced.

## Evidence and provenance limits

The host uses `OPERATOR_NATIVE_RUN_UNATTESTED` as an origin claim. Synthetic tests
execute this actual host with SDK/Indicator doubles, therefore the claim is not
proof of native provenance. The harness report explicitly identifies the execution
as synthetic and checks loaded NinjaTrader assembly count zero.

G's independent Python verifier validates the envelope byte and graph contract.
It retains `native_provenance_attested=false`, `execution_authority=false`,
`certification_evidence=false`, `runtime_admission=false`, and
`zone_rules_independently_reevaluated=false`. Serialized zone hashes are not a
full independent replay of TimeZoneInfo rules, and omitted bars are not
independently reconstructed by the summary verifier.

## Offline validation inventory

86 C# state/ownership/integration cases; 33 successful emitted envelope examples.
123 H pytest cases, including the actual-source SDK compile and structural gates.
865 A-through-H pytest cases in total; 1254 when combined with the preserved
R3/R4/R5/R5.1/R5.2 five-module chain (389 tests).

Examples cover normal/inline/async callbacks, false and exception outcomes,
conditional R1 skips, raw mixed kinds/anomalies, variable row counts, UI/shallow
clones, separate owners, shared directories, repeated events, disabled state,
chart and operator gates, mutations, cancellation during processing/closure,
foreign files, tampering, and no reads after release. Tests do not certify all
possible runtime interleavings or real provider behavior.

The package checks SDK metadata 8.1.8.2 and compiles a library without executing
it. The only executable it launches is compiled against F1's explicit doubles,
not against the native NinjaTrader DLLs. Results must pass on the user's Windows;
repository creation alone is not validation.

## Next gates

Review all R5.3 sources/diffs and preservation, then separately authorize a scoped
local implementation commit. No commit or push is performed by H. Installation
must use an isolated, reviewed target and include all eight authored C# files.
NinjaTrader compilation and source identity are separate checks, followed by
fresh current operator confirmations and a new private capture directory. No
native activation is authorized by this package or this document.

## Primary references

- NinjaTrader: OnStateChange language reference.
  https://ninjatrader.com/support/helpguides/nt8/onstatechange.htm
- NinjaTrader: Understanding the lifecycle of NinjaScript objects.
  https://ninjatrader.com/support/helpGuides/nt8/understanding_the_lifecycle_of.htm
- NinjaTrader: Clone language reference.
  https://ninjatrader.com/support/helpguides/nt8/clone.htm

## Local H1 harness correction

The original H package passed SDK compilation but failed four of 86 synthetic
cases before promotion: success_clone_active, success_clone_setdefaults,
two_independent_hosts and shared_capture_rejected. Each failed in the test-only
Contents helper while hashing an open matrix writer. File.ReadAllBytes opens a
reader whose sharing mode does not permit the already-existing write handle.
The diagnostic writer itself permits read access and remains unchanged.

H1 changes only that test helper to open FileAccess.Read with FileShare.ReadWrite
and hash the stream. Existing writes are permitted by the reader's share mask;
the helper obtains no write access. All before/after byte-hash, disposal, ownership
and request-count assertions remain. The four original failure cases remain in
the same 86-case inventory. No host, A-G, budget or verifier contract is changed.

The failed H audit, original package and candidate hashes are preserved. The
unchanged host's original SDK reference compilation is reusable; the repaired
harness is recompiled against explicit doubles and the full planned compatibility
suite compiles the host again against installed SDK references without executing
that library. No synthetic success establishes native provenance.

## Local H2 Windows path correction

The first full H1 compatibility run passed 1221 tests and failed all 33 emitted
envelope tests only at the exact file-set assertion: Windows relative paths used
backslashes while the envelope manifest uses forward slashes. Both before/after
inventory keys now use Path.as_posix(). Hashing, exact set equality, immutability,
seal verification, provenance checks and all 33 cases remain unchanged. No file
path on disk, native host, A-G contract or evidence bytes are changed by this fix.
The H1 failed regression and candidates are retained with their hashes.
