# RC3A-R2 explicit configuration publication

`python -B -m tools.publish_sim_native_config_v3` is an operator action, never a
startup hook. Run it as the Windows user who owns the existing CurrentUser DPAPI
authority and NinjaTrader installation. It never provisions or rotates authority.

Required arguments are `--configuration-generation`, `--protection-timeout-us`,
and `--recovery-timeout-us`. Supply the timeouts from the approved backend runtime
configuration. The normal required `APISettings` environment must already be
present. The tool has no fallback to test profiles, and supplies no trading/risk
or timeout defaults. Missing inputs stop publication before any directory write.

The tool loads the canonical SimNativeAccountV3 catalog and composes the existing
disabled runtime without starting it. It compares an independently recomputed
effective policy digest with `NativeAdmissionProducerV3.risk_version()`, the same
method used when producing admission evidence. Its runtime-evidence callback
always rejects; publication never requests evidence or produces an admission.

All paths derive from LocalAppData under `ARMS-AI/sim-native-v3/runtime`:
`commands`, `activations`, `state`, and `reconciliation`. They must be local,
distinct, outside the repository/OneDrive/Custom, and without redirection.
The existing private user/SYSTEM ACL policy is applied, or retained after exact
permission verification. Existing directory contents are never cleaned.

First configuration generation is 1; later operator invocations require prior+1.
The generation is checked again under the existing publisher lock. The underlying
API retains identical-content idempotency; the operator command does not renew an
existing generation. Runtime generation remains the binding's independent value.
Each explicit publication uses current UTC microseconds and exactly 24 hours of
commissioning validity. This grants no trade authorization and changes no
per-trade deadlines. Expired configuration fails closed; only an explicit new
generation can replace it.

HMAC generation, canonical encoding, and readback verification stay in
`sim_native_authority_v3.py`. Successful stdout contains only authenticated public
configuration fields. Failed verification never automatically repairs a torn or
inconsistent pair. Treat any command failure as a blocked commissioning gate.

Manual indicator pins map as follows:

| Indicator property | Verified configuration field |
| --- | --- |
| SelectedAccountName | native_account |
| InstrumentName | instrument |
| CommandDirectory | command_directory |
| ActivationDirectory | activation_directory |
| ControlledAuthorityId | authority_id |
| ControlledBackendAccountId | backend_account_id |
| ControlledConfigurationGeneration | configuration_generation |
| ControlledRuntimeGeneration | runtime_generation |
| ControlledStateDirectory | state_directory |
| ControlledReconciliationDirectory | reconciliation_directory |

No pins should be treated as commissioned until publication and readback pass.
Keep `NATIVE_SUBMIT_ENABLED=false` and `AUTO_RETRY_ALLOWED=false`. The publisher
does not launch NinjaTrader, deploy source, compile, submit, cancel, or flatten.
Source deployment remains gated separately by the RC3A deployment procedure.
