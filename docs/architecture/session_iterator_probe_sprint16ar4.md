# Sprint 16A-R4: isolated SessionIterator comparison

R3 baseline: `c579e9d082c1cf0523c7b9c6aca9f1e83e8e1a41`. That local commit contains exactly the R3 metadata harness, tests and contract review. R4 does not modify the historical exporter, live exporter, adapters, source pins or admission rules.

`ArmsSessionIteratorProbeV1` is a separate opt-in indicator for a later native diagnostic experiment. R4 implementation and validation are offline only. No installation, activation, native capture, production restart, R4 commit or push is part of this phase.

## Recovery and evidence boundary

The initial recovery found a complete probe and synthetic harness, which compiled against both the installed SDK and offline doubles. The continuation recovered all five R4 implementation/test/document files without truncation, with HEAD still at the R3 baseline and no tracked or staged changes. The previous 50-module regression had completed: its log and XML agree on 1,873 passed, zero failures/errors/skips. The prior focused result was 94 passed, zero failures/errors/skips. No prior regression process was still running. Copies, SHA-256 manifests and validation outputs remain private under `.arms-dev/sprint16a-r4/`; they are excluded from commit scope. Existing R2/R3 evidence is preserved.

R2 returned 4,503 rows with NoError. Its first iterator call returned the September 13 22:00Z through September 14 21:00Z session; its second call at end +1 tick returned false. R3 found five built-in bar types using +1 second but did not establish the native false predicate. The exposed offline SDK body cannot reproduce the native first-call success. **Synthetic PASS means only that ARMS diagnostic logic works under supplied doubles. No new native result exists.**

## Request and A/B contract

All four operator settings default to false: ProbeEnabled, MarketReopenConfirmed, NqDataFlowConfirmed and ConnectionStableConfirmed. No request is created unless all are true, the output directory is fresh/local/fixed/non-reparse, the application timezone is UTC, Playback is absent and SDK version is exactly 8.1.8.2. These flags are explicit operator assertions, not automatic observations of market state.

One BarsRequest uses NQ DEC26, expiry 2026-12-01, tick size .25, point value 20, Minute/1 Last, CME US Index Futures ETH in Central Standard Time, Repository lookup, DoNotMerge, reset-on-new-trading-day=true and adjustments=false. Requested date values are September 16 through September 21, 2026, with the same Unspecified request-date representation as R2. No provider fallback, Update subscription, retry, timer, account API, order API, process start or connection mutation exists.

The callback checks instrument, period, request policies, template name/version/timezone and 3–10,002 returned rows. It fingerprints timestamp representations and OHLCV across the bounded snapshot without exporting those bars. Snapshot identity, count, template version and fingerprint must remain stable. A fingerprint establishes consistency within this attempt; it does not attest that the current repository is identical to R2.

| Sequence | Iterator | First query | Second query | Inclusion |
| --- | --- | --- | --- | --- |
| A_TICK | Private instance A | 2026-09-14T00:00:00.0000000Z | First returned end +1 tick | true |
| B_SECOND | Fresh private instance B | Same exact UTC value | First returned end +1 second | true |

B never receives A's iterator. Both receive the same returned Bars object. Explicit reference inequality and synthetic instance/call counters verify the isolation. No IsInSession or IsNewSession calls alter state between the two calls in a sequence. Identity A/B is local to the recorded probe UUID.

A first result permits the second call only when it is true, its bounds are UTC, ordered and exactly match the R2 anchor. Successful second-call bounds must be UTC and match September 14 22:00Z through September 15 21:00Z. False returns retain null bounds; stale native properties are never read after false. Exceptions and partial bound reads are recorded separately. A failed/invalid first call skips that sequence's second call; the other independent sequence can still be observed, but the final outcome remains UNRESOLVED.

Hard limits: **one request, two iterators, at most four GetNextSession calls, 64 records, 8,192 bytes per record, 131,072 JSONL bytes**. Fingerprint material is also bounded. Repeated lifecycle transitions, repeated callbacks, same-thread reentrant callbacks and UI clones cannot launch another experiment. Inline callback completion waits for Request to return successfully before sealing. Termination, changed operator gates/configuration, changed snapshot, output ownership loss or a diagnostic limit/write failure prevents a completion seal.

## Diagnostic evidence and seal

The probe writes only `session-iterator-probe.jsonl` and, after closing that writer, `session-iterator-probe.done.json` via a CreateNew temporary file and rename. The fixed JSONL filename prevents two attempts from owning the same fresh directory. Existing files are never overwritten. A failed write may leave an incomplete JSONL or temporary seal; neither is a completed experiment.

Each row has schema `arms.nt.session-iterator-probe.record.v1`, probe UUID/version, monotonic record sequence, lifecycle/operation state, SDK version, component assembly MVID, fixed target identity, observed application timezone, template version, snapshot identifier/hash, row count and operator confirmations. Call rows also include sequence/iterator identity, zero-based call index, seven-digit query timestamp and Kind, includeEndTime, nullable boolean result, observed bounds and Kinds, bounds validity, fixed guard reason, native call count, exception phase and allowlisted exception type. Messages are either NONE or a fixed redaction string; no native message, stack trace, arbitrary type name, account identifier or output directory is emitted. Early rows explicitly have unverified source identity until validation completes.

The seal uses schema `arms.nt.session-iterator-probe.seal.v1`, with probe UUID/version, SHA-256 of exact closed JSONL bytes, byte/record/call counts, writer_closed=true, diagnostic_complete=true and outcome. All records and seals declare DIAGNOSTIC_ONLY, certification_evidence=false and runtime_admission=false. Diagnostic completion can seal FAIL or UNRESOLVED; it is not historical certification. A PASS string in an unsealed JSONL is not usable evidence.

`tools/verify_session_iterator_probe_v1.py` independently validates bounded bytes, schemas/types, duplicate JSON keys, UUIDs, fixed setup, snapshot equivalence, monotonic records, call counts, A/B instance labels, exact query construction, begin/result pairing, required calls, bounds/Kinds, guards and seal integrity. It recomputes the outcome rather than trusting the recorded string. Missing calls after a valid first result, duplicate/reordered calls, unknown fields, exceptions mislabeled as success, shared iterator labels, malformed evidence, seal mismatch or forged outcome are rejected. A complete, correctly recorded native exception instead verifies as an UNRESOLVED diagnostic run.

Continuation review reproduced a verifier gap: a recomputed seal could accompany contradictory REQUEST_RETURNED outcome metadata and still return PASS. Six regression cases demonstrated insufficient lifecycle validation, premature source-verification metadata and floating-point values accepted as integer sentinels. The verifier now accepts only the component's two complete lifecycle orders: request return before the asynchronous callback, or after the entire inline callback. It binds source verification to SNAPSHOT_VERIFIED, requires integer row/index fields and checks the return-event outcome against callback timing and independent adjudication. Thirteen added corruption cases cover these failures plus missing/truncated records, schema/UUID errors and overflow. The C# probe and harness are unchanged by this continuation.

The seal is an integrity check, not a signature. Neither an assembly MVID, local source hash nor this verifier establishes native provenance. A synthetic transcript can satisfy the same schema. Native collection provenance must be established separately at the later operator review.

## Core adjudication

These outcomes require two equivalent valid first calls and trustworthy, complete evidence. True second results must also pass the bounds guards.

| A second result | B second result | Outcome |
| --- | --- | --- |
| false | true | ADD_ONE_SECOND_NATIVE_CONFIRMATION=PASS |
| false | false | ADD_ONE_SECOND_NATIVE_CONFIRMATION=FAIL |
| true | true | R2_FALSE_RETURN_NOT_REPRODUCED |
| true | false, or incomplete/error/ambiguous setup | NATIVE_CONFIRMATION=UNRESOLVED |

The serialized `native_confirmation` values are PASS, FAIL, R2_FALSE_RETURN_NOT_REPRODUCED and UNRESOLVED. No outcome patches an exporter, admits history, warms analysis, creates a position or enables execution.

The later R4 task explicitly makes this four-call core independently usable. It supersedes the R3 plan's requirement for extended traversal before calling the core comparison confirmed. Optional weekday/maintenance/Sunday-Monday comparisons and a separate traversal capped at 64 calls remain **design only**, requiring separate review; they are not enabled or required here. A native core PASS supports later repair review but does not prove complete calendar coverage or explain the internal false predicate.

## Offline validation

The actual C# component is compiled and run against synthetic SDK doubles without loading NinjaTrader. Tests observe real emitted bytes, seals, exact query ticks, iterator instance counts, bounds reads, request/disposal counts and lifecycle effects. They cover all four outcomes, guard/exception cases, snapshot mutation, limits, duplicate/reentrant callbacks, inline failure after callback, directory ownership, evidence corruption and rejection by the historical certification API.

Structural checks prohibit account/order/process/connection-mutation APIs; the minimal doubles expose no account/order APIs. The UI DisplayAttribute.Order is explicitly distinguished from a trading Order type. The installed SDK compile uses real NinjaTrader Core/Gui assemblies and a name-only Indicator shim deriving the real IndicatorRenderBase; no SDK method or indicator is executed by that compile.

Exact test commands, policy environment, results, file hashes and read-only runtime observations are private under `.arms-dev/sprint16a-r4/`. Production settings are never changed for tests. The proposed R4 commit consists only of the probe, synthetic harness, tests, verifier and this document; it excludes generated binaries, logs, test outputs and runtime evidence.

Continuation validation on September 21, 2026: **107 focused tests passed; 1,886 tests passed across the same 50-module regression scope; zero failures, errors or skips.** Both runs include the installed SDK compile test; Core and Gui metadata report version 8.1.8.2. Six newly added regression cases failed before the verifier fix and passed afterward. The regression covers Sprint 16A/R1/R2/R3/R4, Sprint 15Z, session/calendar, market data and MVP safety using the recovered repository test-policy environment. The two regression warnings concern the existing Starlette/httpx deprecation and pytest JUnit record_property compatibility. Command arrays, explicit test-policy values, logs, XML reports and preservation checks are under `.arms-dev/sprint16a-r4/continuation-audit/`. The continuation did not check current service health, canonical sequence or market/feed/connection state. Native results remain NOT_RUN and +1-second native confirmation remains NOT_YET_OBSERVED.

## Human review and future installation gate

Current market reopen, NQ flow and connection stability are **unconfirmed**. Prior daily maintenance is neither an error nor evidence for or against this iterator hypothesis. Recorded service unavailability is a separate observation and does not establish a feed or NinjaTrader failure. No services are restarted in R4.

Before any later native preparation, the operator must explicitly confirm MARKET_REOPEN_CONFIRMED=YES, NQ_DATA_FLOW_CONFIRMED=YES and NINJATRADER_CONNECTION_STABLE=YES, and separately authorize installation/activation. Use an isolated non-production NinjaTrader 8.1.8.2 environment with existing repository data and a suitable existing chart; use the reviewed template and UTC application timezone. No history download, connection change, account access, production chart reload or production recompile is included. If that environment is unavailable, stop rather than treating the production instance as isolated.

Review the source hash and offline validation, then compile/install only in that separately authorized environment. The probe is disabled by default. Supply a new empty private output directory only at the future gate, enable the three confirmations and one probe attempt deliberately, and inspect its sealed diagnostic output. Do not restart a pending attempt, reuse a directory or infer PASS from an incomplete file. Native recompilation is required for any future installation; no installation has occurred in this phase.

The later offline verification command is:

```text
python -B tools/verify_session_iterator_probe_v1.py --diagnostic <private-directory>/session-iterator-probe.jsonl --seal <private-directory>/session-iterator-probe.done.json
```

Even a verified native PASS returns to human review before any historical traversal edit. Historical bootstrap capture and certification remain separate, gated work.
