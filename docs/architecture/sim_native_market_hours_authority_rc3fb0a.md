# RC3F-B0A: bounded SIM_NATIVE market-hours authority

The existing SIM_NATIVE financial lifespan owner now supplies a separate
authenticated market-hours lifecycle. PAPER providers, environment-driven PAPER
refresh, native execution gates, news, quotes and candidates are unchanged.
Missing or invalid input selects the existing unavailable calendar provider.

## Evidence and scope

The operator must freshly capture `ArmsCalendarEvidenceV1` from NQ DEC26,
Minute/1, UTC application time, CME US Index Futures ETH. No C# changes or
deployment are part of this package. Its 13 native samples and all loaded weekly,
holiday and partial-holiday metadata are compared using `compare_loaded_calendar`
against the existing reviewed template SHA256. The old fixed witness digest is
not a freshness credential. The new witness must be no more than 30 minutes old
at issue and must not be future-dated. An operator-reviewed exact SHA is required.

The package embeds the original witness UTF-8 text and SHA256 so verification can
recheck every field and regenerate the snapshot. Synthetic tests deliberately
change copied timestamps; their results are not production witness certification.
The witness is operator-observed local evidence, not a NinjaTrader signature;
the existing collector does not record GetNextSession's Boolean return. Every
returned sample must nevertheless pass exact UTC bounds and trading-day checks.
Do not edit a failed capture or relabel its DateTime.Kind to make it pass.

V1 only accepts ordinary dates. Every full or partial holiday and its adjacent
civil dates are quarantined. No holiday mapping, empty-event assumption, week-wide
extension, automatic renewal or rollover is introduced. The fixed reviewed NQ
DEC26 profile conservatively refuses coverage on/after December 1, 2026. This is
a bounded commissioning restriction, not a claim about the contract's last trade.

Default coverage is issue-time Chicago date plus two dates; 1–3 dates are allowed.
Expiry is exactly the earlier of issue plus 48 hours and midnight immediately
after the final covered Chicago date. The existing MarketHoursServiceV2 still
decides market open, including daily maintenance and weekends. Package expiry
does not extend the independently verified controlled configuration validity.

## Publication and consumption

`python -B -m tools.certify_sim_native_market_hours_v1 --witness <absolute-private-path> --witness-sha256 <operator-reviewed-sha256> --days 3`

The tool loads the already provisioned CurrentUser DPAPI key, authenticates current
configuration, verifies canonical SIM_NATIVE account/risk/policy identity, and
writes only these create-once files:

* `%LOCALAPPDATA%\ARMS-AI\sim-native-v3\authority-inputs\market-hours-v1.json`
* `%LOCALAPPDATA%\ARMS-AI\sim-native-v3\authority-inputs\market-hours-v1.sig`

HMAC-SHA256 uses its own domain and exact canonical JSON bytes. A torn pair is
unavailable. Publication immediately authenticates readback and rechecks config.
Existing files are never overwritten; explicit retirement/republication is a
separate operator decision. A failed publication retains its lock and any partial
pair for operator review. Publication never starts financial ownership,
creates commands/activations, changes key/config, or invokes NinjaTrader.

Witness and package paths must be fixed local, outside the repository/OneDrive/
Custom, not redirected, and owned by the effective user with ACL grantees limited
to that user and SYSTEM. Template lookup uses the previously audited installation
path under this Windows user's OneDrive Documents; its exact reviewed hash is
required. A different install location or template version needs explicit review.

Runtime lookup authenticates afresh; removal, HMAC damage, changed witness digest,
configuration generation/account/risk/policy drift, expiry or lost coverage
revokes admission. No cached-good or repository-fixture fallback exists. The
30-minute witness budget applies at issue, not repeatedly during package life.

`GET /api/v3/dashboard/sim-native-market-hours-authority` observes this process-wide
owner. It never starts ingestion, publishes, reconciles or renews. Account switches
replace only PAPER's child application; each child's endpoint resolves the same
SIM_NATIVE owner. No production backend restart is performed by this code task.

## Manual fresh capture (required before production certification)

1. As the NinjaTrader Windows user, create a NEW empty directory under
   `%LOCALAPPDATA%\ARMS-AI\sim-native-v3\calendar-captures\<new-run-id>`. Inherit the
   existing private authority-root permissions; do not use the repository or Custom.
2. In NinjaTrader, use an NQ DEC26 chart, Minute value 1, Trading Hours
   `CME US Index Futures ETH`. Verify the application timezone is UTC. If any
   required setting differs, stop rather than silently changing the capture scope.
3. Add the existing `ArmsCalendarEvidenceV1` indicator. Set `Private evidence
   directory` to that new directory. Leave all execution bridge properties alone.
4. Confirm `ARMS_CALENDAR_EVIDENCE_COMPLETE` in NinjaScript Output and one new
   `<session-guid>.calendar.jsonl` file. `FAILED`, missing samples or any validator
   rejection require investigation, never manual evidence editing.
5. Review the artifact, record its SHA256 with `Get-FileHash -Algorithm SHA256`,
   and provide its absolute path and hash within 30 minutes for certification.
   Do not reuse a prior capture just because its metadata matches.

No production authority exists until this fresh input passes explicit publication
and authenticated readback. News and L1 remain separate unsatisfied authorities.

## Offline validation

Targeted tests: `backend/tests/test_sim_native_market_hours_authority_v1.py`.
The module covers strict witness/package mutations, freshness boundaries,
expiry during file reads, bounded coverage, readback/create-once publication,
GET with no disk/execution changes, and process-global isolation across PAPER
account switching. All evidence in these tests is explicitly synthetic.

Related regression modules (under `backend/tests/`):

* `test_loaded_calendar_sprint13.py`, `test_native_calendar_sprint13.py`
* `test_certified_market_hours_snapshot_loader_v2.py`
* `test_certified_market_hours_runtime_provider_v2.py`
* `test_certified_market_hours_data_lifecycle_v2.py`, `test_market_hours_service_v2.py`
* `test_sim_native_financial_runtime_service_v3.py`
* `test_sim_native_financial_checkpoint_v3.py`, `test_sim_native_financial_projection_v3.py`
* `test_sim_native_admission_runtime_evidence_v3.py`, `test_first_controlled_trade_preflight_v3.py`
* `test_sim_native_integration_v3.py`, `test_sim_native_account_authority_v3.py`
* `test_sim_native_authority_v3.py`

Run with `python -B -m pytest -q -p no:cacheprovider`, the existing process-local
test profile and an isolated temporary LOCALAPPDATA. No production publication,
NinjaTrader launch, native compile or native mutation is part of offline tests.
