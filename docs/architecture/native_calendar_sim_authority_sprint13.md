# Sprint 13: offline authority review and remaining native proof

Baseline: `0a1753a2d602fcad2898d1869c6a2c0ac99a137e`. Research and
read-only certification only. Production 90, PAPER 80.5, quality 85 remain
unchanged. No account enumeration, broker calls, account mutation or orders.

## What is established

The installed ETH template is version 5119, SHA-256
`370b17f23eeea694e686394b5fdb9b55681089c22d5232d5e6a354a314325620`.
Its five Sunday-through-Thursday 17:00 starts end the following day at 16:00,
in Windows `Central Standard Time`. The portable evidence preserves all 13
2026 exception entries, including native early/late flags and constraints.
The local database has both stock and futures NQ definitions. Installed enum
metadata identifies Future=0; the unique futures row is version 8591, tick .25,
point value 20 and the same ETH template. The stock row is excluded. Only these
public instrument columns were read; no account table was accessed.

[NinjaTrader holiday semantics](https://ninjatrader.com/fr/support/helpGuides/nt8/using_the_trading_hours_window.htm)
apply holidays to trading-day sessions. A full holiday removes that trading
day's sessions; an early close changes its EOD end. This is not equivalent
to closing the entire same civil date. The existing civil-date special-window
representation cannot safely represent an early close plus the next trading
day's evening reopening in one window. Exception dates and their adjacent
civil dates therefore remain outside the ordinary capture validator.

[SessionIterator](https://docs.ninjatrader.com/ninjascript/sessioniterator)
must be tied to Bars after DataLoaded. Its exchange trading date differs
from civil date for overnight sessions. Detailed boundary documentation uses
configured timezone while the overview mentions PC timezone; the collector
preserves wall values and DateTime.Kind, records both timezone IDs, and never
labels ambiguous native wall values UTC. Compare native boundaries with
Windows Central Standard Time and Python America/Chicago, including the
November DST probes, before issuing a calendar certificate.

## Capture specification and limits

`native_capture_spec_sprint13.json` binds Provider31, NQ DEC26, UTC close
labels, the reviewed ETH file hash, and a finite ordinary capture interval:
September 21 00:00 UTC through September 28 00:00 UTC. The extra civil-date
coverage supports boundary lookups; it does not extend contract validity.
It cannot be extended by silently adding dates, exceptions or a new contract.
December 1 expiry is month metadata, not a certified final trading day.

The harness validates the feed fields and exact source artifact before
watching a new session, then checks the artifact again after capture. It
reports next scheduled boundary and trading date independently of ticks and
provider connectivity. Unknown state fails closed. Calendar identity is a
separate prerequisite: a file hash and matching template name do not prove
the same calendar is loaded in native Bars. The CLI therefore stops before
watching files or creating a service while that binding is pending. There is
no operator boolean or spec field that bypasses this gate. A future reviewed
binding validator must consume the native metadata before capture is enabled.

The startup sidecar audit now rejects a later quarantine after alignment,
loss callbacks, and CONTINUE records contradicting callback state. A strategy
decision or profitable signal is no longer a transport-certification gate.
Existing OHLCV, freshness, duplicate, ordering and canonical HTF checks remain.
Daily-boundary certification requires HTF bars from the current reopened
session; retained pre-close HTF bars cannot satisfy the milestone.
The unchanged exporter may present a stale pre-close bar on the first reopen
tick; the reader must reject it, not relabel it fresh. Native boundary tests
may reveal this pending behavior; no speculative exporter relaxation is made.

Machine-readable plans specify start windows, durations, evidence, pass,
fail and inconclusive conditions. Daily capture is 8,700 seconds. Market-open
capture is 7,500 seconds. A continuous Friday-to-Sunday capture needs 185,100
seconds and is explicitly **design-only**: it exceeds the current 10,800-second
harness bound. Do not concatenate separate captures as continuous proof.
Holiday capture is blocked pending native exception mapping. November 26 is
only a template-sourced candidate, not a certified exchange schedule.

## Next human action: calendar metadata only

No account or order configuration is needed. Do not repeat the closed-market
exporter smoke. Native ticks and market opening are not required for this step.

1. WINDOW: NinjaTrader Control Center. MENU: New > NinjaScript Editor.
2. In Indicators, create `ArmsCalendarEvidenceV1` using the new-indicator wizard.
   Replace the generated indicator source with the repository file
   `integrations/ninjatrader/ArmsCalendarEvidenceV1.cs`. Compile (F5).
   Do not replace `ArmsReadOnlyMarketV1` or enable a strategy.
3. WINDOW: the ARMS NQ DEC26 chart. MENU: right-click > Data Series.
   FIELD/VALUES: Instrument NQ DEC26; Type Minute; Value 1; Trading hours
   CME US Index Futures ETH. Application timezone remains UTC.
4. MENU: right-click chart > Indicators. Select `ArmsCalendarEvidenceV1` and
   Add. FIELD: Private evidence directory. VALUE: the existing private
   `.arms-dev/ninjatrader-current` directory inside the ARMS-AI repository.
   BUTTON: OK. This is a one-shot DataLoaded capture; no 30-second wait.
5. Remove that calendar indicator after completion. Preserve its new
   `UUID.calendar.jsonl` and all existing evidence. Tell Codex completion only;
   do not paste contents, identifiers or personal paths into chat.

Codex must inspect schema/content, immutable file hash, contract, installed
versus loaded session definitions, all 2026 exception flags/constraints,
iterator end-inclusion semantics, DST and trading dates. The collector emits
no prices or accounts and declares `PENDING_REVIEW`; its existence is not a
certificate. No native capture was performed during this sprint.

Only after calendar review may a private spec resolve the portable template
reference through the existing private path map. Start the harness before one
fresh exporter session. Use new isolated state/output files; no old-session
replay. Do not claim full lifecycle certification from an ordinary session.

## Account proof boundary

Reflection-only metadata inspection of NinjaTrader.Core 8.1.8.2 found no
explicit public simulation property. No getters on account instances or
Account.All were invoked. Public Account.Provider, Connection and AccountStatus
are candidates; AccountStatus values describe operational status, not class.
Simulator parameters and UI Global Simulation Mode do not prove an API object
is incapable of real execution.

[Account Class documentation](https://docs.ninjatrader.com/ninjascript/account_class)
shows account access, but does not establish the immutable account-bound proof
required here. [Simulation documentation](https://ninjatrader.com/support/helpguides/nt8/trading_in_simulation.htm)
describes Sim101 routing; a matching label is not sufficient identity evidence.
Provider.Simulator alone remains insufficient. Multi-factor checks cannot
turn several unproven hints into authoritative classification.

Accordingly, native classification is UNKNOWN and discovery remains blocked.
No account discovery adapter is implemented. Do not open Accounts or enumerate
accounts merely to repeat name/provider evidence. The next account prerequisite
is an official vendor contract identifying an immutable account-bound simulation
invariant for this installed API, including ownership, rename and reconnect
semantics. This may require vendor clarification; no message was sent.

Conditional future workflow: after that contract and market-data certification,
review a bounded scalar-only discovery adapter, then obtain authorization for
one read-only native discovery. No native Account object or order method may
cross its interface. The operator would activate only that reviewed collector;
Codex would read its private local evidence. Exact account-discovery UI controls
are deliberately not invented before such an adapter exists.

## Private binding design

The committed schema has no identifiers and forces enabled=false. Future
configuration belongs outside Git under private `.arms-dev`, with owner-only
access. Bind exactly one account object and its owning connection. Persist
domain-separated installation-keyed HMAC references; never plain account
names or unsalted hashes. The key stays private. A canonical configuration
hash detects drift but is not proof of provenance by itself.

Revalidate authoritative proof, exact object/connection/provider identity,
installation, label fingerprint, configuration hash and a <=15-second snapshot
on every use. No accounts, multiple accounts, wildcard selection, stale or
future timestamps, mismatch, rename or reconnect revoke eligibility. Recovery
requires a new explicit review, never automatic rebinding.

The executable contract in `sim_binding_contract_v1.py` tests hypothetical
**synthetic** proof only. Native input always returns UNKNOWN. Even the passing
synthetic case has external_order_authority=false and SIM execution disabled.
No code in the discovery contract submits, changes, cancels, flattens or resets
anything. Dashboard projections expose statuses only, with no identifiers.

## Remaining certification boundary

Closed-market transport and shutdown evidence remain intact. Native loaded
calendar, market-open 1m/15m/1h, daily/weekly/holiday/DST transitions, deliberate
disconnect/reconnect, authoritative SIM proof and future private discovery
remain pending. No SIM/LIVE execution readiness follows from this sprint.
