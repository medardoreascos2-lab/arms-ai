# SIM_NATIVE Commissioning Policy V1

The operator approved `backend/config/sim_native_commissioning_policy_v1.json`
for disabled SIM_NATIVE commissioning only. Its ten API settings and two
timeouts are not PAPER/LIVE defaults. TOPSTEP_150K remains the canonical unchanged
financial profile. The loader rejects unknown/missing/duplicate keys, wrong
schema/version, bool numeric inputs, non-finite values, invalid bounds, more than
one open position, and non-increasing recovery timeouts. It never changes the
environment or global APISettings behavior.

The commissioning policy ID is SHA-256 over the canonical normalized policy JSON
(sorted keys, compact encoding, floating-point API fields normalized to floats).
It is audit evidence, not authentication, and is reported outside the signed V3
configuration. No configuration schema or C# changes are required.

The existing admission risk_version remains the digest of the canonical profile
digest and NativeAccountSafetyV3.policy_digest. That policy digest currently
covers effective ArmsSettings, not the ten APISettings or recovery timeouts.
Consequently, changing those commissioning inputs changes the commissioning
policy ID, while the existing risk_version may remain unchanged. The publisher
independently recomputes and compares the runtime risk_version; it does not
redefine its contract.

The risk-inventory regression also requires refreshing the recorded AST evidence
for RC3A-R2's extraction of `NativeAdmissionProducerV3.risk_version()`: the source
hash, delegated call, and dictionary keys now inside the helper. This changes
only that existing inventory row's derived evidence, not its safety classification
or any risk-inventory assertion.

After repository/range certification and with NinjaTrader closed, invoke the
committed publisher as the Windows user who owns the existing DPAPI authority:

```powershell
py -B -m tools.publish_sim_native_config_v3 --commissioning-policy-v1 --configuration-generation 1
```

The flag explicitly selects the committed policy, passes all ten API fields and
both timeouts to the disabled runtime, and prohibits timeout overrides. The
legacy explicit-timeout mode is retained. The output wraps verified public
configuration fields with commissioning_policy_id; this wrapper is not written
to the native configuration file. No authority is created or rotated.

Generation 1 receives exactly 24 hours from publication. No automatic renewal is
installed. A later generation requires separate operator authorization. The
publisher never starts runtime execution or NinjaTrader and never creates an
admission/order/activation. Keep both native submit and auto-retry constants false.

Deployment requires an external backup, exact four-file source/destination
hashes, the committed duplicate/reference gate, and a final safety check. Do not
edit NinjaTrader.Custom.csproj or suppress missing project Compile entries to
claim the gate passed. Manual NinjaScript discovery/compilation is a distinct
operator step, and any remaining project gate errors must be reported.
