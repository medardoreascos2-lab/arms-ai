"""ASGI-owned native financial ingestion; no production admission authority."""
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock

from backend.accounts.sim_native_account_v3 import SimNativeAccountV3
from backend.services import sim_native_authority_v3 as authority
from backend.services.sim_admission_envelope_v3 import utc_us
from backend.services.sim_native_commissioning_policy_v1 import load as load_policy
from backend.services.sim_native_runtime_v3 import build_native_sim_runtime
from backend.services.sim_native_command_spool_v2 import SimNativeCommandSpoolV2
from backend.services.sim_native_financial_projection_v3 import SimNativeFinancialProjectionV3
from backend.services.sim_native_financial_checkpoint_v3 import execution_values, native_phase
from backend.services.sim_native_financial_diagnostic_v3 import SimNativeFinancialDiagnosticV3, stage, phase_generation


def admission_not_composed():
    raise RuntimeError("SIM_NATIVE_ADMISSION_NOT_COMPOSED")


class SimNativeFinancialRuntimeServiceV3:
    def __init__(self, *, clock=None):
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()
        self._started = False
        self._runtime = None
        self._integration = None
        self._projection = None
        self._configuration = None
        self._diagnostic = SimNativeFinancialDiagnosticV3()
        self._view = self.unavailable()
        self.cadence_seconds = None

    @staticmethod
    def unavailable():
        return {"execution_domain": "SIM_NATIVE", "status": "UNAVAILABLE",
                "reason": "SIM_NATIVE_FINANCIAL_UNAVAILABLE"}

    def _verify(self):
        values = authority.verify_config(binding=self._runtime.binding, paths=self._paths,
            risk_version=self._runtime.lifecycle.native_admission_producer_v3.risk_version(),
            configuration_generation=int(self._configuration["configuration_generation"]),
            now_us=utc_us(self.clock()))
        if values != self._configuration:
            raise ValueError("native configuration changed; explicit restart required")

    def _record_failure(self, exc):
        runtime = self._runtime
        try:
            configuration_generation = int(self._configuration["configuration_generation"]) if self._configuration else None
        except (KeyError, TypeError, ValueError, OverflowError):
            configuration_generation = None
        self._diagnostic.record(exc,
            runtime_generation=runtime.binding.runtime_generation if runtime else None,
            configuration_generation=configuration_generation,
            checkpoint=runtime.store.account_namespace if runtime else None,
            projection=self._projection.path if self._projection else None)

    def start(self):
        with self._lock, self._diagnostic.operation():
            if self._started:
                return
            self._started = True
            try:
                binding = SimNativeAccountV3.load(execution_domain="SIM_NATIVE", provider="Simulator", native_account_name="Sim101")
                if (binding.backend_account_id != "SIM_NATIVE-917E15181DBB4F8F8D625716795704A3"
                        or binding.instrument != "NQ DEC26" or binding.runtime_generation != 1
                        or binding.risk_profile_id != "TOPSTEP_150K"):
                    raise ValueError("unapproved native financial identity")
                policy = load_policy()
                if (policy.protection_timeout_us, policy.recovery_timeout_us) != (10_000_000, 60_000_000):
                    raise ValueError("unapproved native observation cadence")
                self.cadence_seconds = policy.protection_timeout_us / 4_000_000
                root = authority.authority_root() / "runtime"
                self._paths = {field: authority.safe_path(root / name, authority=True)
                    for field, name in zip(authority.PATH_FIELDS, ("commands", "activations", "state", "reconciliation"))}
                self._financial_root = authority.safe_path(root / "financial", authority=True)
                with stage("AUTHORITY_LOAD"):
                    key = authority.load_authority()
                with stage("CONFIG_VERIFY"):
                    self._configuration = authority.read_authenticated_config()
                with stage("RUNTIME_BUILD"):
                    self._runtime = build_native_sim_runtime(binding=binding, namespace_root=self._financial_root,
                        authority_key=key, runtime_evidence=admission_not_composed,
                        api_settings=policy.api_settings, protection_timeout_us=policy.protection_timeout_us,
                        recovery_timeout_us=policy.recovery_timeout_us)
                with stage("CONFIG_VERIFY"):
                    self._verify()  # No financial writes before verified config.
                with stage("CHECKPOINT_START"):
                    self._safe_checkpoint_paths()
                    self._runtime.store.start()
                self._projection = SimNativeFinancialProjectionV3(store=self._runtime.store,
                    path=self._financial_root / "dashboard-projection.json")
                with stage("PROJECTION_APPLY"):
                    self._projection.rebuild()
                spool = SimNativeCommandSpoolV2(root=self._paths["command_directory"].parent)
                if spool.commands_dir != self._paths["command_directory"]:
                    raise ValueError("command spool pin mismatch")
                self._integration = self._runtime.integration(spool=spool,
                    activation_directory=self._paths["activation_directory"], phase_directory=self._paths["state_directory"],
                    receipt_directory=self._paths["reconciliation_directory"], event_bus=self._projection)
                self.observe()
            except Exception as exc:
                self._view = self.unavailable()
                self._record_failure(exc)
                if self._runtime is not None:
                    self._runtime.store._durability.release()
                self._integration = None

    def observe(self):
        """Called by lifespan worker only, never by GET. Failure latches unavailable."""
        with self._lock, self._diagnostic.operation():
            if self._integration is None:
                return
            try:
                with stage("CONFIG_VERIFY"):
                    self._verify()
                    for path in (*self._paths.values(), self._financial_root):
                        authority.safe_path(path, authority=True)
                with stage("CHECKPOINT_START"):
                    self._safe_checkpoint_paths()
                with stage("PHASE_VERIFY"):
                    self._preflight_phases()
                with stage("PHASE_APPLY"):
                    self._integration.reconcile()
                with stage("SERVICE_PUBLISH"):
                    self._view = self._capture()
            except Exception as exc:
                self._view = self.unavailable()
                self._record_failure(exc)
                self._integration = None
                self._runtime.store._durability.release()

    def _safe_checkpoint_paths(self):
        path = self._runtime.store.account_namespace
        for suffix in ("", ".tmp", ".lock", ".evidence.json", ".evidence.json.tmp"):
            authority.safe_path(path.with_name(path.name + suffix), authority=True)

    def _preflight_phases(self):
        # Reject a poisoned batch before applying even its earlier valid phases.
        store = self._runtime.store
        previous = {}
        with stage("PHASE_DISCOVERY"):
            files = sorted(self._paths["state_directory"].glob("*.state"))
        for number, path in enumerate(files, 1):
            authority.safe_path(path, authority=True)
            if path.name != f"{number:08d}.state" or path.stat().st_size > 1_048_576:
                raise ValueError("native phase gap or size")
            with stage("PHASE_READ"):
                with path.open("rb") as stream:
                    wire = stream.read(1_048_577)
            with stage("PHASE_VERIFY"):
                phase = native_phase(wire, store._authority_key, store.admission_digest)
            phase_generation(int(phase["generation"]))
            store.binding.assert_claims(phase)
            if not store.admission or phase.get("operation_id") != store.admission["operation_id"] or int(phase["generation"]) != number:
                raise ValueError("unbound native phase")
            observations = {k: v for k, v in phase.items() if k.startswith("execution.")}
            if any(observations.get(k) != v for k, v in previous.items()):
                raise ValueError("contradictory native execution history")
            roles = []
            for execution_id, value in observations.items():
                role, _, order_id = execution_values(value)
                roles.append(role)
                if (phase.get("order_id." + role) != order_id or phase.get("entry_filled") != "1"
                        or phase.get("submit." + role) != "1"
                        or (role != "ENTRY" and phase.get("exit_filled") != "1")
                        or (role == "RECOVERY_CLOSE" and phase.get("recovery_id") != "a3." + store.admission_digest[:32] + ".R")
                        or (execution_id in store._native["executions"] and store._native["executions"][execution_id] != value)):
                    raise ValueError("native execution identity changed")
            if roles.count("ENTRY") > 1 or len(roles) - roles.count("ENTRY") > roles.count("ENTRY"):
                raise ValueError("unmatched or duplicate execution")
            previous = observations
        if files and any(previous.get(k) != v for k, v in store._native["executions"].items()):
            raise ValueError("native evidence rollback")

    def _capture(self):
        store = self._runtime.store
        store.receipt()
        state = store.capture_state()
        store.validate_state(state=state)
        projection = self._projection.read()
        if set(projection["events"]) != set(store._native["outbox"]):
            raise ValueError("projection incomplete")
        portfolio = state["account_portfolio"]
        opened, closed = portfolio["open_positions"], portfolio["closed_positions"]
        position = (closed or opened or [None])[0]
        roles = [execution_values(value)[0] for value in store._native["executions"].values()]
        role = next((role for role in roles if role != "ENTRY"), "ENTRY" if roles else None)
        binding = self._runtime.binding
        result = {"execution_domain": "SIM_NATIVE", "backend_account_id": binding.backend_account_id,
            "native_account": binding.native_account_name, "provider": binding.provider, "instrument": binding.instrument,
            "runtime_generation": binding.runtime_generation, "status": "CLOSED" if closed else "OPEN" if opened else
                "AWAITING_EXECUTION" if store.admission_digest else "NO_OPERATION",
            "open_position_count": len(opened), "closed_position_count": len(closed),
            "journal_count": len(self._runtime.lifecycle.trade_journal_v2.trades),
            "realized_pnl": position["realized_pnl"] if position else 0,
            "unrealized_pnl": position["unrealized_pnl"] if position else 0,
            "order_role": role, "exit_reason": role if closed else None,
            "last_financial_event_id": projection["last_financial_event_id"],
            "processed_event_count": projection["processed_event_count"],
            "pending_dashboard_events": len(set(store._native["outbox"]) - set(store._native["delivered"])),
            "observed_at": self.clock().isoformat(), "observation_maximum_age_seconds": self.cadence_seconds,
            "configuration_expires_us": int(self._configuration["expires_us"])}
        for field in ("position_id", "direction", "quantity", "entry_price", "stop_loss", "take_profit", "exit_price"):
            result[field] = position.get(field) if position else None
        return result

    def get_snapshot(self):
        # Only immutable published observations; no filesystem or reconciliation.
        with self._lock:
            view = deepcopy(self._view)
            if view["status"] != "UNAVAILABLE":
                now = self.clock()
                age = (now - datetime.fromisoformat(view["observed_at"])).total_seconds()
                if (utc_us(now) >= view["configuration_expires_us"] or
                        not 0 <= age <= self.cadence_seconds):
                    return self.unavailable()
                view["observation_age_seconds"] = age
            return view

    def stop(self):
        with self._lock:
            if self._runtime is not None and self._runtime.store._durability._lease is not None:
                self._runtime.store._durability.release()
            self._integration = None
            self._view = self.unavailable()
