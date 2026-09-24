# R5.3-E — SDK request and cursor bridge

Status: offline bridge, not a NinjaScript Indicator or an authorized native run.
Consumes the exact A/B/C/D components without modifying them.

## What this layer does

SessionTimestampNativeRequestV1 wraps an already-created, exclusively-owned
NinjaTrader.Data.BarsRequest. Its Identity is that actual object. Submit forwards
native sender identity and maps ErrorCode.NoError to success; it never forwards
provider messages. It submits once and disposes once, including disposal errors.
A shallow clone cannot submit or dispose the original. A disposal request while
Submit is still executing is rejected. C remains the exclusive lifetime owner,
including coordination of operations in flight. Late callbacks after disposal
are ignored; earlier duplicates are delivered to C's fail-closed controller.

SessionTimestampNativeCursorFactoryV1 binds one Bars object and one A plan.
Only controls belonging to that exact plan can construct an iterator. The native
constructor is SessionIterator(Bars), not the TradingHours overload. Constructor
attempts are counted even if the native constructor throws, with no slot retry.
The cursor Identity is the underlying SessionIterator, not an invented UUID.

DateTime ticks/Kind and includeEndTime must equal the selected plan control and
are passed through without conversion. Only R0 may be used again, as R1, after
true with readable, same-Kind, positive-order bounds. No other reuse is allowed.
No bounds are read before true, after false/exception, out of order, or twice.
Native exceptions are allowed to reach B, which records safe exception types.

The bridge enforces its own ceilings of 11 constructor attempts and 12 method
attempts, in addition to B's limits. Mandatory lifecycle checkpoints and context
callbacks run before every constructor, method or bounds getter. Context failure
latches the bridge unusable, so B's next context checkpoint stops completion.
Reentrant use, wrong queries, invalidated resources or wrong plan membership are
rejected before extra native actions. Clones cannot invalidate their original.
Cancellation is cooperative, not an atomic cancellation of an SDK call already
in progress; B/C prevent a cancelled operation from becoming a successful seal.

## Tests versus native evidence

The executable uses explicit doubles with the NinjaTrader namespaces. It does
not load NinjaTrader assemblies. Each recorded native-like call and getter is a
SYNTHETIC counter in those doubles, compared with B and E's counters. Calling
these tests is not an experiment on actual GetNextSession semantics.

A second command compiles A/B/C/D/E as a library against the installed Core/Gui
SDK and framework references. That DLL is never loaded or executed here.
Compilation establishes API compatibility, not successful native runtime use.
The installer checks Core/Gui assembly metadata for 8.1.8.2 without executing
assembly code and hashes them. It does not change the NinjaScript installation.

Successful synthetic integration samples go through A plan -> E wrapped request
-> C lifecycle -> B executor -> E SDK-double cursors -> D writer/seal -> unchanged
D Python verifier. False and native-like exception outcomes can be diagnostic
success, without implying a trading calendar is correct. No origin is native.

## Still required before a real run

The future host must construct/configure the one request, enforce all operator
and runtime gates, verify actual loaded instrument/period/Repository/DoNotMerge
settings and dates, select the returned Bars object and fingerprint it, validate
loaded template/calendar/zone rules, and bind the selected source timestamps.
It must supply real validators, not the no-op synthetic validators used in tests,
revalidate before/after the matrix and preparation, manage Indicator cloning and
termination, invalidate the bridge when its Bars request lifetime ends, and call
PublishSeal only after C is ready and the complete native context is verified.

This bridge neither constructs a BarsRequest nor validates its configuration,
calendar, timestamps or environment itself. It cannot independently attest the
meaning of Unspecified, omitted bars, template identity or native provenance.
A full native-context evidence binding/verifier and a disabled-default Indicator
remain to be implemented. No repair, data admission or execution is authorized.

## Reference contracts reviewed

Official NinjaTrader documentation, consulted for this implementation:
- https://ninjatrader.com/support/helpguides/nt8/barsrequest.htm
- https://ninjatrader.com/support/helpguides/nt8/request.htm
- https://ninjatrader.com/support/helpguides/nt8/getnextsession.htm
- https://ninjatrader.com/support/helpguides/nt8/actualsessionbegin.htm
- https://ninjatrader.com/support/helpguides/nt8/actualsessionend.htm

These docs support the method/property surfaces. They do not establish the
version-specific predicate responsible for the earlier R2/R4 false return.
