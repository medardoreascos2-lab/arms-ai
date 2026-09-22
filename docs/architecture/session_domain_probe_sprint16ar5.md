# Sprint 16A-R5: bounded SessionIterator domain diagnostic

Status: implemented and offline validated only. The design is committed as `236ad7a6a874797f8dd3f0d01a2482de80050a30`; this implementation is not committed, installed, or activated. No native R5 results exist. Preserve the committed R4 probe and its completed native evidence. Do not replace the historical exporter's tick increment with a second increment.

## Components and authority

* `integrations/ninjatrader/ArmsSessionDomainProbeV1.cs`: independent, disabled-by-default NinjaScript indicator.
* `tools/verify_session_domain_probe_v1.py`: independent, bounded offline verifier; standard library only, no NinjaTrader execution.
* `backend/tests/fixtures/session_domain_probe_harness_sprint16ar5.cs`: synthetic doubles that execute the actual authored R5 source without loading NinjaTrader assemblies.
* `backend/tests/test_session_domain_probe_sprint16ar5.py`: synthetic behavior, corruption rejection, preservation, structural safety, installed-template encoding and SDK compilation checks.

All evidence is `DIAGNOSTIC_ONLY`, `certification_evidence=false`, `runtime_admission=false`. Findings describe observations; `root_cause` always remains `UNRESOLVED`. Neither a completed diagnostic nor any finding authorizes historical admission, a behavioral repair, or execution. No account, order, ATM, execution, connection mutation, realtime subscription, timer, or service-control API is used.

The only request is repository-only NQ DEC26, Minute/1 Last, September 16 through September 21, 2026, DoNotMerge, CME US Index Futures ETH, reset enabled, split/dividend adjustment disabled. SDK 8.1.8.2, application timezone UTC, no Playback, and all three explicit operator confirmations are mandatory. Revalidate the environment, request and returned Bars identities before each call and before completion. A later human gate must supply the fresh local fixed-drive, non-reparse private output directory. This phase creates no native attempt directory.

## Coverage and template binding

Scan 3–10,002 returned timestamps, requiring native Utc Kind, minute alignment and strictly increasing order. Never relabel Kind. Persist first/last timestamp and Kind, up to 32 UTC-date buckets, six reviewed expected-session buckets, four intervening weekday maintenance buckets, an after-first-session bucket, boundary checkpoints, and outside-interval count. Each populated bucket has count and first/last source indices and timestamps. Session buckets additionally retain the earliest eligible interior timestamp/index. The first and last returned rows remain explicitly marked as potentially partial.

This is bounded summary evidence, not a timestamp or OHLCV export. Scan all rows to compute the summaries; do not serialize all rows. Snapshot fingerprints cover native timestamp representations, Kinds and OHLCV and are checked after the matrix and again before sealing. A fingerprint binds inputs but cannot reconstruct timestamps omitted from the summaries. The verifier checks summary and checkpoint consistency; it cannot independently attest native provenance or reconstruct every underlying bar.

The six template expectations are trading days September 14, 15, 16, 17, 18 and 21. The first expected bounds are September 13 22:00Z through September 14 21:00Z; next expected bounds are September 14 22:00Z through September 15 21:00Z. These are template expectations until observed through a native call. Membership uses Minute close labels `(begin, end]`; coverage counts never establish complete session data or complete candles.

Bind these expectations to the actual returned `bars.TradingHours`: name, version, timezone, weekly schedule, relevant timezone offsets, and absence of holiday overrides in September 13–21. Retain canonical weekly sessions plus all holiday dates and partial-holiday constraints/sessions, excluding descriptions, with its SHA-256. Installed Session times use **HHmm**, not HHmmss. The canonical payload is capped at 10,000 UTF-8 bytes; collection limits and the record cap also apply. A changed or incompatible loaded template fails closed. No separate disk template lookup supplies the constructor control.

## Fixed matrix and conditional controls

All query Kinds are Utc. Calls include the end timestamp unless stated otherwise. Every direct case has a fresh iterator; only R1 reuses R0's iterator. No session helper is called before a direct query.

| Case | Query | Condition / construction |
| --- | --- | --- |
| R0 | September 14 00:00Z | Fresh Bars iterator R; established first-session anchor |
| R1 | R0's end plus one second | Same iterator R, only after valid R0; otherwise explicit skip |
| G | September 14 21:00:01Z | Fresh Bars iterator; equivalent gap query without prior iterator state |
| N | September 14 22:00:01Z | Fresh Bars iterator; expected next-session interior |
| C | Actual earliest eligible returned interior timestamp | Fresh Bars iterator; source index must be 1 through Count−2 and inside a reviewed post-first session; skip when absent |
| E_TRUE | September 14 21:00:00Z, include=true | Fresh Bars iterator, only if G=false and N has valid expected bounds |
| E_FALSE | Same exact endpoint, include=false | Separate fresh Bars iterator under the same predicate |
| T_NEXT | Same query as N | Fresh iterator from returned `bars.TradingHours`, only if next-session label count is zero or N=false while C succeeds with valid bounds |

Hard limits: **eight GetNextSession invocations, seven iterator construction attempts, one BarsRequest**. Exceptions consume the attempted call budget. Failed prerequisites produce fixed skip reasons, never replacement calls or retries. False results never trigger stale bound reads. Unexpected exceptions, non-Utc successful bounds, reversed bounds or successful bounds outside the case's reviewed expectations terminate without a completion seal. E_FALSE accepts either reviewed adjacent session as an observation; it does not assume which session the API should select.

Observational findings can coexist:

* `SNAPSHOT_COVERAGE_FAILURE`: no post-first data or no eligible actual interior control. This is a diagnostic coverage limitation, not proof the repository is empty.
* `MAINTENANCE_GAP_QUERY_FALSE`: fresh G returned false.
* `DIRECT_NEXT_SESSION_QUERY_FALSE`: N returned false.
* `ITERATOR_REUSE_DIFFERENCE` / `FRESH_ITERATOR_SAME_RESULT`: R1 and G differ / agree in their recorded Boolean and bounds.
* `CONSTRUCTOR_CONTEXT_DIFFERENCE`: T_NEXT and N differ in their recorded Boolean or bounds.
* `UNRESOLVED`: missing anchor/control or otherwise no supported distinguishing observation.

A gap false result is not a maintenance-gap root cause. A constructor difference does not prove a Bars-coverage restriction. Comparison to R4 also requires checking snapshot fingerprint equality; this implementation records the fingerprint without treating a changed snapshot as the same historical input.

## Evidence and offline verification

The probe writes only `session-domain-probe.jsonl` and, after successful completion, `session-domain-probe.done.json` via a temporary seal. Limits are 96 records, 16 KiB per record and 256 KiB JSONL. The fixed seal is under the verifier's 4 KiB limit. The writer is flushed and closed before seal publication; output ownership is rechecked. Inline callbacks cannot seal before Request returns successfully. Duplicate/reentrant callbacks cannot rerun the matrix, and UI clones cannot release the owner's resources.

Schema names are `arms.nt.session-domain-probe.record.v1` and `arms.nt.session-domain-probe.seal.v1`. Records bind probe UUID, request/snapshot identity, component MVID, configuration, template and snapshot hashes, exact query representations, iterator identity and construction mode, per-case result/bounds/guards, counters, coverage and lifecycle. Native/provider exception text is always redacted.

The separate verifier validates exact fields/types, UUIDs, configuration and hash consistency, bounded coverage/checkpoint graphs, template payload, mandatory/conditional cases and skip reasons, independent identities, exact query strings, call/iterator/request budgets, lifecycle, and independently recomputed findings. It rejects missing/truncated/unsealed evidence, extra or contradictory records, duplicate JSON keys and recomputed seals over inconsistent records. Hash integrity is not provenance authentication.

Offline invocation, **only after a separately authorized native capture exists**:

```text
python -B tools/verify_session_domain_probe_v1.py --diagnostic <capture>/session-domain-probe.jsonl --seal <capture>/session-domain-probe.done.json
```

## Offline validation and next gate

Focused tests execute the actual C# against synthetic doubles, including all 64 combinations of gap/next/constructor results, anchor availability and coverage availability, plus fail-closed lifecycle, output ownership, budget, template, coverage and evidence mutations. An installed XML check catches HHmm/HHmmss mismatches independently of the doubles. SDK compilation references the installed Core/Gui 8.1.8.2 assemblies without executing their native methods. Synthetic results are not native proof.

The recorded repository policy environment is used for the focused and existing 50-module regression selection, covering Sprint15Z, Sprint16A/R1/R2/R3/R4, calendar/session, market data, execution-risk and MVP safety. Exact command/environment and results remain private under `.arms-dev/sprint16a-r5/implementation/` and are excluded from commit scope.

Stop after offline validation. Review these five implementation files before any implementation commit or installation approval. Installation/compilation in NinjaTrader and activation are separate later gates. Do not reapply, remove or modify R4; do not modify either exporter or FreshNativeAdapter. Future activation requires fresh human confirmation of reopened market, NQ flow and stable connection; no earlier confirmation is inferred to satisfy that gate.
