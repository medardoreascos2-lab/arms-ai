# Sprint 14R: built-in Sim101 authority and bounded witness

Baseline: `dee3e8f85254e8c6d581ce6e3175491400838977`.

The built-in account's documented purpose is simulation. The reviewed public
contract does not establish an account-bound origin invariant strong enough to
identify that object in a potentially ambiguous runtime collection. No
`PROVEN_BUILTIN_SIM101` acceptance path is implemented. Generic classification
remains `PROVEN_SIMULATION`, `PROVEN_NON_SIMULATION`, or `UNKNOWN`; UNKNOWN is
ineligible. The exporter, market certification, thresholds, and execution policy
are unchanged.

## Official guarantees and remaining uncertainties

| Topic | Supported conclusion | Limit |
|---|---|---|
| Default account | [Sim101 documentation](https://ninjatrader.com/support/helpGuides/nt8/the_sim101_account.htm) identifies the platform's default simulated account. | A purpose statement does not identify an arbitrary runtime object carrying the same metadata. |
| Removal | [Accounts tab](https://ninjatrader.com/support/helpguides/nt8/accounts_tab.htm) explicitly excludes Sim101 from Remove Account. | This is a supported UI restriction, not a promise about database recovery, recreation or object identity. |
| Rename | Name and Display Name are distinct documented columns. The reviewed sources do not establish immutable internal-name semantics. | SDK public setters do not establish that supported UI renaming is allowed. A disabled UI field would not prove global API immutability. |
| Additional simulators | [Multiple simulation accounts](https://ninjatrader.com/support/helpGuides/nt8/multiple_simulation_accounts.htm) documents user-created simulation accounts. | Simulation does not imply built-in identity. |
| API selection | [Account API](https://docs.ninjatrader.com/ninjascript/account_class) demonstrates exact-name selection from Account.All. | An example lookup is not a documented collision-proof origin discriminator. |
| Collection lifetime | [Official support response](https://forum.ninjatrader.com/forum/ninjatrader-8/strategy-development/1278189-run-many-strategies-in-the-same-account-name?p=1278193) explains that Account.All can include disconnected accounts. | Presence alone does not prove a current connection, ownership or eligibility. |
| Routing/ownership | [Simulation trading](https://ninjatrader.com/support/helpguides/nt8/trading_in_simulation.htm) describes selected-account routing. | The reviewed contract does not define an immutable built-in-object/connection association across restart or reconnect. Live data-provider identity is not account simulation proof. |
| Reset | [SimulationAccountReset](https://docs.ninjatrader.com/ninjascript/simulationaccountreset) notifies reset and Playback rewind/fast-forward; sender is an Account. | A reset event is not unique built-in attestation. Do not cause a reset to test identity. |
| Playback | [Playback setup](https://ninjatrader.com/support/helpGuides/nt8/set_up12.htm) describes Playback101 copying Sim101 settings and resetting on connection. | These behaviors must not be generalized to Sim101 identity persistence. |

The Sprint 14 declaration audit found public setters for Name, DisplayName,
Provider and Connection, string constants rather than a canonical account-object
handle, and no accepted generic simulation property. This is metadata inspection,
not an experiment on accounts. No supported rename, reset, reconnect, deletion,
recreation or restart experiment was performed. Those lifecycle guarantees remain
unproven where the sources above are silent.

## Witness boundary

`ArmsSim101WitnessV1` is a separate indicator. After offline certification, the
operator reported successful host compilation and activated it once. Adjudication
reads only its completed file; it does not call the native account API.
Its output is a new UUID `.sim101-witness.jsonl` in an existing private directory.
It uses a monotonic 30-second deadline, five-second samples, at most eight records
including END, and passive reset subscription. It does not depend on ticks.

Only the unique exact built-in-name candidate is pinned. No identifiers or display
names leave the boundary: output contains candidate count, equality booleans,
documented enum values, observation UUID, sequence and timing. The UUID identifies
an observation, not an account. Account and connection references are private.
Nonblocking registry checks prevent waiting on both registries; replacement never
silently rebinds the source. Two scalar reads detect some concurrent changes but
are not an atomic snapshot or proof of continuous identity between samples.

The witness checks Simulator account-provider metadata and Provider31 connection
metadata independently. Provider31 is this observation's context, not a universal
built-in-account invariant. A disconnected or differently associated built-in
account can fail these preconditions; that does not classify it non-simulation.
Even full consistency emits `CANDIDATE_CONSISTENT_NOT_PROVEN`, generic UNKNOWN,
future eligibility false and execution DISABLED. A counterfeit object matching
all weak factors would also remain unproven.

Reset of the candidate, unidentified reset, unknown metadata, ambiguity,
replacement, mismatch, registry contention, expiry or host termination ends the
observation. An unrelated identified reset is ignored. Cleanup latches stop,
unsubscribes reset, disposes timers, clears native references, writes END, and
disposes the writer. END records observable cleanup attempts, not proof that a
subsequent writer disposal succeeded. Offline tests additionally verify exclusive
read access after completion and no late callback writes. No native cleanup claim
is made before a run.

The compiled Cbi call allowlist contains only Account collection/name/provider/
connection/status getters, Connection registry/options/status getters, provider
enum getter, and reset-event add/remove. There are no account setters, order,
cancel, flatten, financial, position, execution or reset calls in the witness.
This is a reviewed code boundary, not a sandbox for NinjaTrader's entire SDK or
process. Raw SDK Account objects have mutators; the witness never exports them.

## Offline certification and privacy

The test module compiles the complete source against metadata-only doubles with
no financial or mutation API. Deterministic cases cover real/external/prop-like
name collisions, user-created Sim names, provider-only claims, missing/ambiguous
candidates, replacement, connection changes, unknown values, instability, reset,
termination, deadline crossing, record limits and cleanup. Generic binding tests
reject the unsupported narrow proof label, including stale and mismatched claims.

An additional test compiles against installed Core/Gui SDK declarations pinned by
Core SHA-256 and scans compiled method/constructor IL in reflection-only mode.
An empty Indicator alias derives from the installed IndicatorBase; this verifies
SDK compatibility, not host deployment or generated NinjaScript wrappers. No
native account object is instantiated or property getter invoked by that audit.
Native host compilation is an operator step. Official-source links and scalar
audit assertions contain no private identifiers, credentials or personal paths.

Run the Sprint 13 market-certificate `tests.modules` list plus Sprint 14 authority
and Sprint 14R witness tests using the existing isolated certification environment.
Frontend and certified market-runtime files are unaffected.

Pre-capture offline validation: 1,084 tests passed in 374.73 seconds across those 38
modules, including Sprint 10/11T/12/13/14, native market certification, freshness,
HTF, MVP and safety regressions. The finalized witness suite separately passed
39 tests in 4.16 seconds after strengthening the queued-callback record-limit
case. The existing Starlette/httpx deprecation warning remains. Installed-SDK
compilation and the compiled Cbi call allowlist passed. Frontend tests/build were
not rerun because no frontend or API code changed. Whitespace checks passed for
tracked files and all four new files. All 109 unrelated untracked files, 16
datasets and 11 original native artifacts retain their recorded hashes; all 17
later native evidence prefixes remain intact. At that offline stage no actual
account access or deployment was performed. The later operator-activated witness
did read scalar account metadata; it made no account mutation or broker/order call.

## Completed activation procedure (historical; do not repeat)

The procedure below has now been completed once. It is retained for traceability,
not a request for another capture. No reset, reconnect or account configuration
was required or authorized. The run cannot resolve the missing origin guarantee
or authorize private binding.

1. WINDOW NinjaScript Editor; MENU New Indicator; VALUE `ArmsSim101WitnessV1`;
   replace its source with `integrations/ninjatrader/ArmsSim101WitnessV1.cs`;
   BUTTON Compile. Stop if compilation fails.
2. WINDOW Control Center; MENU New > Chart; FIELD Instrument VALUE NQ DEC26;
   FIELD Type VALUE Minute; FIELD Value VALUE 1; FIELD Trading hours VALUE
   CME US Index Futures ETH; BUTTON OK. Use a separate diagnostic chart, leaving
   the existing exporter/chart unchanged. Keep existing UTC and Provider31 setup.
3. WINDOW diagnostic chart; MENU Indicators; select ArmsSim101WitnessV1;
   BUTTON Add; FIELD Private witness directory VALUE the existing private
   `.arms-dev/ninjatrader-current` directory under the repository (resolve to an
   absolute local path); BUTTON OK. This starts the single read-only capture.
4. Leave this diagnostic chart active for 35 seconds. Do not visit account/order
   windows or trigger a reset. Report completion; evidence will be inspected
   directly. No JSON copying is needed. Do not repeat a failed/inconclusive run
   without a genuinely new observation reason.

No private binding is created. Runtime binding revalidation has not run. Any
future eligibility still requires an accepted origin proof, private binding and
runtime revalidation together. No output from this witness satisfies the first
requirement. SIM execution remains DISABLED and LIVE authority remains NO.

## Native adjudication

The fresh artifact was identified by `arms.nt.sim101-witness.v1` content, its
observation UUID and timestamp, then bound by SHA-256
`0045efc938f4a9d8be98849fc6c1934b170535752b8ca8e35fd81b082dd0359c`.
Observation UUID `c17fbf57-6c19-4547-98c6-bfa849ab354a` is not an account identifier.
The private raw file remains unchanged and is not part of the proposed commit.

START is `2026-09-21T04:04:06.2339837Z`; END is
`2026-09-21T04:04:36.2413116Z`, reason `WINDOW_END`. Seven complete, newline-ended
JSON records have contiguous sequence 0 through 6, one START, five samples and one
END, with no duplicate or out-of-order records. Stopwatch elapsed at END is
30.0142725 seconds; START-to-END wall duration is 30.0073279 seconds. All six
metadata records were written before the 30-second deadline. The 14.2725 ms END
dispatch delay is recorded as observed, without changing any runtime policy.

Every metadata sample has exactly one candidate, the same pinned account and
connection, matching before/after samples, registered connection, account provider
Simulator and connection provider Provider31. Account, connection and price-feed
statuses are Connected. No candidate change or ambiguity was observed. Equal
payloads at successive sample times are expected consistency observations, not
duplicate records. The last metadata sample is at elapsed 25.0496463 seconds;
END carries cleanup flags, not another account sample. These observations do not
prove continuous identity between samples or through the unsampled final interval.

END reports reset unsubscription, timer disposal and released references. A
read-only exclusive open succeeded after completion, supporting writer closure.
The file remained unchanged across audit reads. Timer cleanup flags are
self-reported, not independently inspected in the host. No selected/unidentified
reset triggered termination; reset capability and semantics were not exercised.
Unrelated resets would be ignored by this witness. No restart/reconnect scenario
was captured; the file cannot exclude transient changes between samples.

Privacy review found exactly the reviewed scalar schema and no actual account
identifier, name, display alias, balance, position, execution, order or credential.
Host compilation is operator-reported; this schema contains no compiled-binary
attestation. The reviewed source and offline SDK call audit are separate evidence.

Result: **NATIVE_WITNESS_CONSISTENCY=PASS**,
**CANDIDATE_CONSISTENT_NOT_PROVEN**, **BUILTIN_SIM101_IDENTITY=NOT_PROVEN**,
**GENERIC_SIM_CLASSIFICATION=UNKNOWN**. Private binding remains absent, runtime
binding revalidation has not run, and future eligibility remains false. Native
read-only account access occurred in the operator's capture; adjudication itself
only reads that evidence. The generic contract and native source are unchanged.

## Shortest safe next path

| Path | Decision and missing requirement |
|---|---|
| A: more native evidence | Repeating these same scalar observations cannot establish origin. Another witness would be justified only after identifying a vendor-supported, account-bound discriminator or simulator-only routing capability that this capture does not expose. Do not reset/reconnect to manufacture evidence. |
| B: vendor-supported binding | Preferred route to native integration. Obtain a supported contract tying the selected runtime object to local-only simulation routing, including collision, rename, replacement, reset, restart and reconnect behavior. Then implement private binding and revocation against that contract. Operator selection records intent; it cannot substitute for origin proof. |
| C: local test-only Sim101 binding | Not implemented. There is no structural proof that the observed tuple cannot also describe non-simulation origin. A name/provider allowlist, acknowledgement, installation hash or process pinning does not establish routing isolation. A structurally isolated ARMS paper engine with no native Account or broker submission bridge can support a local-only MVP, but that is not native Sim101 eligibility. |
| D: another NinjaTrader environment | Playback101 is documented simulation with distinct execution behavior. The reviewed documentation does not provide a stronger account-bound API attestation for our boundary. Provider.Playback or an account label alone cannot solve the same origin problem. A future architecture with an independently established simulator-only capability needs its own review; none is enabled here. |

[Global Simulation Mode](https://ninjatrader.com/support/helpguides/nt8/global_simulation_mode.htm)
documents restrictions in order-entry interfaces; the reviewed text does not
establish an unbypassable AddOn Account API sandbox.
[Playback](https://ninjatrader.com/support/helpguides/nt8/playback.htm) documents
replay and simulator execution behavior, not the needed identity attestation.
Neither setting was changed or activated during this adjudication.

The shortest safe operational MVP path is continued existing ARMS local PAPER and
read-only market-data work, with no NinjaTrader account made eligible and no native
order bridge. This is a recommendation, not new execution authorization. In
parallel, a vendor answer to the following question could unblock native binding:

> Which supported read-only API or simulator-only capability binds a runtime
> Account object to the built-in local simulator and prevents routing to a broker,
> even with colliding or mutable names/provider metadata? Please specify supported
> identity and revocation behavior across reset, replacement, restart and reconnect.

This is a draft question only; no message was sent to NinjaTrader. No repeat
capture or account action is requested. Native SIM execution, external SIM account
testing and LIVE remain blocked; a further offline/local PAPER sprint is possible
under separately defined scope. The proposed commit contains only the four Sprint
14R source/test/audit/document files; raw native evidence stays private.

Adjudication regression: **327 passed, 0 failed, 0 skipped in 32.78 seconds**.
The exact ten modules are recorded in the audit JSON's
`adjudication_validation.modules`; invocation was `py -m pytest <modules> -q`
with the existing isolated certification environment and private dataset mapping.
This includes the hash-bound native capture check, three new native-claim
non-promotion cases, Sprint 14/14R, binding/readiness, MVP, current PAPER,
execution ownership, risk precedence, financial state and frozen market-open
certification. SDK compilation and compiled-call allowlisting were rerun by the
witness suite without native account access. Only the existing Starlette/httpx
deprecation warning remains. Frontend is unaffected. Diff checks passed for all
four proposed files, and all preservation checks passed again. Index remains
empty; no commit or push has occurred. Scoped commit authorization is pending.
