# ARMS AI — R5.4 — bounded SessionIterator timestamp-domain repair

## Status

Design only.

No production repair is authorized by this document.

No exporter mutation.
No stored-bar timestamp conversion.
No historical admission.
No PAPER or LIVE execution authority.

## Evidence motivating R5.4

R5.3 native evidence demonstrated that `DateTime.Kind` alone does not
explain the prior R2/R4 `GetNextSession(false)` behavior.

The decisive family was C, one tick after the prior session boundary:

- C_U:
  raw clock preserved as `Unspecified`;
  `GetNextSession` returned false.

- C_LUTC:
  identical ticks/clock fields, only `Kind` labeled UTC;
  `GetNextSession` returned false.

- C_THUTC:
  source clock interpreted in the loaded TradingHours timezone and explicitly
  converted to UTC;
  `GetNextSession` returned true with readable valid bounds.

R1 also returned false when reusing the R0 iterator with the same-ticks
LUTC query, while N returned true for the explicit next-session UTC reference.

Therefore R5.3 supports the narrower statement:

> For the tested boundary query, explicit TradingHours-zone interpretation
> changed observed SessionIterator behavior, while changing DateTime.Kind
> without changing ticks did not.

R5.3 does NOT establish that every `Unspecified` timestamp universally means
TradingHours-local time.

## Objective

Design and later test a narrowly scoped query-domain adapter used only at the
SessionIterator query boundary.

The adapter must never silently rewrite the source Bars timestamps.

Conceptual boundary:

    raw Bars/query clock
            |
            | preserved unchanged
            v
    SessionIterator query adapter
            |
            | explicit, reviewed interpretation
            v
    UTC query for GetNextSession

## Proposed component

Candidate name:

`SessionIteratorQueryDomainAdapterV1`

The eventual implementation may use another reviewed name, but must preserve
the contract below.

## Inputs

The adapter receives:

- the source query DateTime
- the exact loaded `TradingHours`
- an explicit conversion policy
- diagnostic provenance describing why conversion was requested

No global/application timezone may substitute for `TradingHours.TimeZoneInfo`.

## Candidate policy

R5.4 must test this policy before any production use:

### UTC input

If source `Kind == Utc`:

- preserve clock fields
- preserve ticks
- do not reconvert
- record `conversion_performed=false`

### Unspecified input

If source `Kind == Unspecified` and the caller explicitly selects the
TradingHours-wall-clock interpretation:

- preserve the original source value separately
- treat its clock fields as wall-clock values in `TradingHours.TimeZoneInfo`
- reject invalid local times
- reject ambiguous local times unless a later reviewed policy explicitly
  resolves them
- derive a new UTC query value
- record source ticks, result ticks, offset and conversion provenance

### Local input

`DateTimeKind.Local` is rejected in the first candidate implementation.

R5.4 must not infer that the machine-local timezone is the intended market
calendar timezone.

## Mandatory preservation

The adapter must not modify:

- Bars objects
- Bars timestamps
- OHLCV values
- historical files
- historical exporter output
- original R2/R3/R4/R5/R5.1/R5.2/R5.3 evidence
- TradingHours definitions
- system timezone
- NinjaTrader connection state

Original values must remain independently inspectable before and after the
candidate query conversion.

## Fail-closed conditions

Reject rather than guess when:

- TradingHours is null
- TradingHours.TimeZoneInfo is null
- timezone identity changes during the operation
- input Kind is Local
- wall-clock input is invalid in the source timezone
- wall-clock input is ambiguous
- arithmetic overflows
- conversion leaves DateTime supported range
- caller requests an unsupported interpretation policy

No fallback to `DateTime.ToUniversalTime()` is permitted.

No fallback to the Windows/application local timezone is permitted.

## R5.4 offline test matrix

The initial implementation package must test at least:

1. UTC identity preservation.
2. Unspecified wall-clock conversion using Central Standard Time.
3. Exact R5.3 A clock.
4. Exact R5.3 B clock.
5. Exact R5.3 C clock (+1 tick after boundary).
6. UTC N reference.
7. Invalid DST wall-clock rejection.
8. Ambiguous DST wall-clock rejection.
9. Local Kind rejection.
10. Null TradingHours rejection.
11. Null timezone rejection.
12. Timezone mutation detection.
13. Overflow/range rejection.
14. Original input ticks unchanged after conversion.
15. No Bars/OHLCV mutation.
16. No account/order/connection API surface.

## Required R5.3 regression expectations

The candidate repair must reproduce the following distinctions without changing
the source values:

- C raw/same-ticks path remains capable of reproducing the observed false.
- C TradingHours-to-UTC candidate query corresponds to the successful R5.3
  THUTC path.
- UTC N remains unchanged.
- Merely relabeling Kind without changing ticks is not accepted as a repair.

This is a regression contract, not authorization to normalize arbitrary data.

## Native confirmation gate

After offline tests pass, a later separately authorized native diagnostic must
compare:

1. preserved/raw query
2. same-ticks UTC-label query
3. candidate TradingHours-zone-to-UTC query

using isolated SessionIterator instances and bounded call counts.

The native confirmation must prove:

- source timestamps remain byte/tick identical before/after
- only the query value is transformed
- candidate behavior matches R5.3 expectations
- no extra retries are introduced
- no hidden conversion occurs outside the adapter

## Production integration gate

Even if native confirmation passes, production integration requires a separate
review.

R5.4 does not authorize changing:

- historical exporter semantics
- historical admission rules
- market-data persistence
- strategy timestamps
- risk timestamps
- journal timestamps
- order/execution timestamps

The first eligible production integration point, if later approved, is only the
code path that constructs query values passed to SessionIterator.

## Safety

R5.4 implementation must contain:

- zero Account API use
- zero Order API use
- zero ATM API use
- zero execution authority
- zero connection mutation
- zero automatic trading
- zero retry loops
- zero exporter mutation

`LIVE_EXECUTION=NO`

## Current authority state

The R5.3 native run remains diagnostic evidence only:

- execution_authority=false
- runtime_admission=false
- certification_evidence=false
- native_provenance_attested=false

R5.4 must not upgrade those claims merely because the candidate adapter passes.

## Completion criteria for R5.4 design

The design is complete when:

- the repair boundary is explicit
- preservation requirements are explicit
- unsupported inputs fail closed
- R5.3 causal observations are encoded as regression expectations
- native confirmation remains a separate gate
- no production implementation is implied

Implementation requires a new explicit authorization after design review.
