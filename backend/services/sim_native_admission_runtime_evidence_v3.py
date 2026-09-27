"""Read-only admission evidence. A digest identifies evidence; it is not authority."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone

from backend.accounts.sim_native_account_v3 import SimNativeAccountV3, digest
from backend.services import sim_native_authority_v3 as authority
from backend.services.sim_admission_envelope_v3 import utc_us
from backend.services.sim_native_commissioning_policy_v1 import load as load_policy
from backend.services.sim_native_dashboard_reader_v3 import SimNativeDashboardReaderV3, _age
from backend.market_data.sim_operator_binding_v2 import _MAX_EVIDENCE_AGE


class SimNativeAdmissionRuntimeEvidenceV3:
    def __init__(self, *, runtime, configuration, policy, clock=None):
        self._runtime = runtime
        self._configuration = deepcopy(configuration)
        self._policy = policy
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def inspect(self):
        """Return bounded observations and, only on PASS, trusted producer claims."""
        view = {"status": "NOT_READY", "reason": "AUTHORITY_UNAVAILABLE",
                "config_valid": False, "config_expired": None,
                "risk_version_match": False, "policy_id_match": False,
                "risk_profile": None, "risk_version": None, "commissioning_policy_id": None}
        observation = SimNativeDashboardReaderV3(clock=self.clock).get_snapshot()
        # The full files stay private to evidence validation, never in the endpoint.
        for key in ("execution_domain", "backend_account_id", "native_account", "provider", "instrument",
                    "heartbeat_fresh", "physical_test_readiness", "position_state", "active_order_count",
                    "controlled_v3_configured", "config_signature_valid", "reconciliation_fence",
                    "native_submit_enabled", "auto_retry_allowed", "observed_at"):
            view[key] = observation.get(key)
        # Derived from the certified bootstrap contract, not a new heartbeat field:
        # BootstrapControlledV3 sets observation-only before it can publish configured.
        view["controlled_observation_only"] = True if observation.get("controlled_v3_configured") is True else None
        view["controlled_observation_only_source"] = "CERTIFIED_BOOTSTRAP_INVARIANT"
        try:
            binding = SimNativeAccountV3.load(execution_domain="SIM_NATIVE", provider="Simulator", native_account_name="Sim101")
            if (binding != self._runtime.binding or binding.instrument != "NQ DEC26"
                    or binding.runtime_generation != 1 or binding.risk_profile_id != "TOPSTEP_150K"):
                view["reason"] = "CANONICAL_BINDING_MISMATCH"
                return view, None
            view["risk_profile"] = binding.risk_profile_id
            policy = load_policy()
            if (policy != self._policy or asdict(policy.api_settings) != asdict(self._runtime.lifecycle.runtime_admission_v2.settings)):
                view["reason"] = "COMMISSIONING_POLICY_MISMATCH"
                return view, None
            view.update(policy_id_match=True, commissioning_policy_id=policy.policy_id)
            risk_version = self._runtime.lifecycle.native_admission_producer_v3.risk_version()
            view["risk_version"] = risk_version
            view["reason"] = "CONFIG_AUTHENTICATION_FAILED"
            config = authority.read_authenticated_config()
            view["reason"] = "CONFIG_VALIDITY_INVALID"
            view["config_expired"] = utc_us(self.clock()) >= int(config["expires_us"])
            if view["config_expired"]:
                view["reason"] = "CONFIG_EXPIRED"
                return view, None
            view["risk_version_match"] = config.get("risk_version") == risk_version
            if not view["risk_version_match"]:
                view["reason"] = "RISK_VERSION_MISMATCH"
                return view, None
            root = authority.authority_root() / "runtime"
            paths = dict(zip(authority.PATH_FIELDS, (root / n for n in ("commands", "activations", "state", "reconciliation"))))
            view["reason"] = "CONFIGURATION_PIN_OR_VALIDITY_MISMATCH"
            verified = authority.verify_config(binding=binding, paths=paths, risk_version=risk_version,
                configuration_generation=int(self._configuration["configuration_generation"]), now_us=utc_us(self.clock()))
            if verified != config or verified != self._configuration:
                view["reason"] = "CONFIGURATION_CHANGED"
                return view, None
            view["config_valid"] = True
            commissioning = observation.get("commissioning")
            if commissioning is None:
                view["reason"] = observation["reason"]
                return view, None
            if any(commissioning[k] != config[k] for k in ("configuration_generation", "runtime_generation", "authority_id")):
                view["reason"] = "COMMISSIONING_GENERATION_OR_AUTHORITY_MISMATCH"
                return view, None
            if observation["status"] != "HEALTHY":
                view["reason"] = ("NOT_READY_SESSION_CLOSED" if observation["status"] == "SESSION_CLOSED"
                                  else observation["reason"])
                return view, None
            # Authentication can take time. Freshness must still hold at return.
            now = self.clock()
            if max(_age(observation["observed_at"], now), _age(commissioning["observed_at"], now)) > _MAX_EVIDENCE_AGE.total_seconds():
                view.update(heartbeat_fresh=False, reason="HEARTBEAT_STALE")
                return view, None
            if utc_us(now) >= int(config["expires_us"]):
                view.update(config_valid=False, config_expired=True, reason="CONFIG_EXPIRED")
                return view, None
            evidence = {**binding.claims(), "account": binding.native_account_name, "provider": binding.provider,
                "instrument": binding.instrument, "runtime_generation": str(binding.runtime_generation),
                "connected": True, "position_quantity": 0, "active_orders": [],
                "sim_runtime_revalidation": "PASS", "sim_execution_authority": "DISABLED",
                "observed_at": observation["observed_at"],
                "runtime_ref": digest({"runtime": observation["runtime"], "commissioning": commissioning,
                    "binding": binding.claims(), "configuration_generation": config["configuration_generation"],
                    "risk_version": risk_version, "policy_id": policy.policy_id})}
            view.update(status="PASS", reason=None)
            return view, evidence
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, OverflowError):
            # No arbitrary messages, key bytes, signatures, admission wires or paths.
            return view, None

    def __call__(self):
        view, evidence = self.inspect()
        if evidence is None:
            raise RuntimeError("SIM_NATIVE_ADMISSION_EVIDENCE_UNAVAILABLE:" + view["reason"])
        return evidence
