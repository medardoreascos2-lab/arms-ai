# Sprint 14: SIM proof remains blocked; offline boundary prepared

Baseline: `696cf4dbdc9dcd4defc4c5c0a53c4e32b044a30f` on
`refactor/backend-architecture`. No native accounts were enumerated or read.
The existing chart, exporter, timestamp policy, calendar and market certification
sources are unchanged. Production 90, paper 80.5 and quality 85 are unchanged.

## Findings and authority limits

Reflection-only inspection of NinjaTrader.Core 8.1.8.2 reviewed declarations for
Account, Connection, ConnectOptions, Provider and AccountStatus. Assembly SHA256:
`89d30ce74dfb21c26c0819db1f5979799b152d522bbfbc436a3b2cfb495b9408`.
No instance getters, static field values, account collections, constructors,
order methods or account databases were accessed. The machine-readable audit is
`backend/tests/account_authority_sprint14.json`.

The expanded audit adds public fields and methods to Sprint 13's property review.
Account has public setters for Name, DisplayName, Provider, Connection, status and
simulation parameters. `SimulationAccountName` is a mutable static string;
other simulation/playback name constants are strings, not pinned account objects.
The status enum describes availability/restriction, not simulation origin.
`Connection.Options` is `ConnectOptions`; `IsDataProviderOnly` describes a
connection capability, not the origin of every associated account.

The [official Account API](https://docs.ninjatrader.com/ninjascript/account_class)
exposes metadata and trading methods on the same object. Its name-based Sim101
lookup example is not an account-origin attestation. Raw Account instances expose
Submit, Cancel, Change, CreateOrder and Flatten; they must never cross a future
discovery boundary. Resetting a simulation account to test its class is a mutation
and is prohibited.

The [Accounts tab guide](https://ninjatrader.com/support/helpguides/nt8/accounts_tab.htm)
describes local simulation accounts, editing settings and Sim101's removal
restriction. These UI facts do not specify an immutable read-only API discriminator.
The [multiple simulation accounts guide](https://ninjatrader.com/support/helpGuides/nt8/multiple_simulation_accounts.htm)
allows multiple local simulation accounts and activation on a subsequent data
connection. Thus neither collection cardinality nor a connection alone proves
origin. A live data feed can support simulation; feed state and account class are
separate facts.

The [Simulated Data Feed guide](https://ninjatrader.com/support/helpGuides/nt8/simulated_data_feed_connection.htm)
describes generated market data. That is data provenance, not sufficient proof of
an arbitrary account object's order routing. [Playback setup](https://ninjatrader.com/support/helpGuides/nt8/set_up12.htm)
describes Playback101 inheriting Sim101 settings and resetting on reconnect;
[Playback processing](https://ninjatrader.com/support/helpguides/nt8/playback.htm)
has distinct execution timing. Playback therefore cannot substitute for the
requested future SIM account proof.

Conclusion: no reviewed documented, account-bound, non-mutating discriminator
establishes simulation or non-simulation for this integration. This is a limit of
the reviewed contracts, not a claim that no such vendor contract can exist.
Provider.Simulator, a simulation-looking name, simulator parameters, UI mode,
operator consent and private allowlisting do not become authoritative by being
combined. Native classification remains UNKNOWN, always ineligible. Observing
more of the same weak fields cannot resolve this semantic gap.

## Implemented offline boundary

`sim_binding_contract_v1.py` accepts exact built-in scalar dictionaries and rejects
nested/native handles and callables without invoking their attributes. No native
bridge, account API, file reader or mutation method is imported. Native claims
always remain UNKNOWN, including claims labelled PROVEN_SIMULATION or
PROVEN_NON_SIMULATION. Only explicitly synthetic offline tests exercise those two
proven classifications. They are not native certification.

A stateless private binding match no longer grants even synthetic future
eligibility. The offline latch additionally requires an explicitly reviewed
process reference, connection epoch, connected state, fresh timestamp, contiguous
discovery sequence starting at zero and non-regressing observation time. A
mismatch, stale/future sample, gap, duplicate, disconnect, changed process or
connection epoch permanently revokes that latch. A restarted consumer cannot
resume a prior sequence; an explicit new review is required. No serialized latch
or automatic restoration/rebinding exists. A caller cannot use this model to
enable native discovery or execution; execution authority is always DISABLED.

This certifies the scalar/status boundary only. It does not certify a native
Account collector. No collector is deployed merely to produce inconclusive
name/provider metadata. Submit/cancel/flatten/position/account mutation are
unreachable through the implemented SIM interface. Existing unrelated PAPER
command routes retain their authentication and behavior.

## Private binding preparation

The existing `private_sim_allowlist_schema_sprint13.json` remains an inert draft
schema. The new validator rejects additional keys, lists, wildcards, cleartext
references, unknown proof contracts, enabled drafts and mismatched configuration
fingerprints. A binding is exactly one object with four 64-hex opaque references,
an enum-shaped provider, unresolved proof contract and `enabled=false`.
Fingerprint is SHA256 of canonical sorted compact JSON for the seven
PrivateBindingV1 fields, excluding schema and the fingerprint itself.

No populated private binding, identifier or key was created or committed.
Future storage must be outside Git, owner-only, and use installation-keyed,
domain-separated HMAC references. The validator cannot prove ACLs, HMAC origin,
account identity or authenticity of a self-reported fingerprint. Those must be
established by a separately reviewed collector and explicit private binding flow.
No production loader is activated before that review. A hash is change detection,
not simulation proof.

## API and dashboard

GET `/api/v2/paper/sim-readiness` returns constant safe statuses without even
requesting a market snapshot. The current PAPER dashboard merges the same statuses
into its projection without modifying the certified market runtime. Runtime
revalidation is explicitly NOT_PERFORMED. The frontend allowlists SIM status
values; injected identifiers, nested objects and unreviewed authority claims are
not rendered as SIM statuses. Neither GET can start discovery or execution.

## Operator gate and remaining work

No NinjaTrader activation is requested. Keep the certified chart/exporter unchanged.
The next useful action is to obtain the vendor's supported contract for this
exact question (no account identifier or screenshot is needed):

> In NinjaTrader 8.1.8.2, which supported read-only account-bound property or
> invariant distinguishes a local simulation account object from a broker-owned
> or Playback account? Please specify rename, connection ownership, live-feed,
> restart and reconnect semantics, without using name/provider alone and without
> submitting, cancelling, changing, flattening or resetting anything.

After reviewing that contract: implement a bounded collector with an explicit
getter allowlist; compile it against the bound assembly; inspect its reachable
calls for mutation and privacy; test its scalar boundary; then provide precise
operator activation steps. Only then may private actual metadata be observed.
Bind one proven account locally, revalidate identity/configuration/epochs at
runtime, and revoke on any mismatch. That later observation still grants no order
authority. No orders, account configuration or discovery should be performed now.

Daily/weekly/holiday/reconnect market certifications remain pending independently.
Sprint 14 does not invalidate the bounded Sprint 13 market-open result and does
not declare SIM discovery, private actual binding or execution readiness.

## Validation

Tests cover the Sprint 13 classification matrix plus lifecycle replay, restart,
reconnect, stale/future evidence, binding changes, private draft validation,
hostile handles, API side effects and frontend status privacy.

- Backend: 1,044 passed in 377.09 seconds, with the existing Starlette/httpx
  deprecation warning. Exact modules: the `tests.modules` array in
  `backend/tests/market_open_native_certification_sprint13.json`, plus
  `backend/tests/test_sim_authority_sprint14.py`; command `py -m pytest <modules> -q`.
  Used the existing isolated `paper_rc_certification_sprint08.json:test_environment`
  and private dataset mapping. No production configuration was changed.
- Finalized Sprint 14 boundary suite: 32 passed, including the subsequently added
  static no-native-bridge/no-mutation check. This is an additional focused run,
  not 32 additional unique tests beyond the broad regression.
- Frontend: `node --test src/lib/*.test.mjs` passed 31 tests;
  `npm.cmd run lint` and `npm.cmd run build` passed. The first sandboxed build
  could not download the existing Google Fonts; the network-enabled retry passed.
- `git diff --check`: PASS. Native compilation: not applicable, no native source
  changed. The frozen market certification source hashes passed their regression.
- Preservation: 136 original protected file hashes unchanged (109 unrelated
  untracked files, 16 datasets, 11 original native artifacts); all 17 currently
  captured native file prefixes also unchanged. The running exporter may append.

Changed files are the SIM contract, current PAPER API, runtime execution inventory,
Sprint 13 binding tests, Sprint 14 audit and tests, frontend projection and its
tests, and this document. No populated binding, account identifier, credentials,
private path, sensitive connection name or native account data is included.
