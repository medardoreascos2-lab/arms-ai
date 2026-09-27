"""Explicit disabled-SIM composition: existing command spool, native phases, outbox.

Keys and native account claims are supplied by trusted composition, never by a
command or callback. This module does not provision secrets or invoke an SDK.
Publication is an explicit write operation, never a GET/dashboard side effect.
"""
from base64 import b64encode
from pathlib import Path

from backend.services.sim_admission_envelope_v3 import AuthenticatedAdmissionV3, utc_us
from backend.services.sim_native_command_protocol_v2 import SimNativeCommandProtocolV2
from backend.services.sim_native_command_spool_v2 import SimNativeCommandSpoolV2
from backend.services.sim_native_financial_checkpoint_v3 import execution_values, native_phase
from backend.dashboard.trade_lifecycle_dashboard_event_publisher_v2 import TradeLifecycleDashboardEventPublisherV2


class NativeSimIntegrationV3:
    def __init__(self, *, runtime, spool: SimNativeCommandSpoolV2, activation_directory,
                 phase_directory, receipt_directory, event_bus):
        from backend.services.sim_native_runtime_v3 import NativeSimRuntimeV3
        if type(runtime) is not NativeSimRuntimeV3 or type(spool) is not SimNativeCommandSpoolV2:
            raise ValueError("explicit isolated SIM_NATIVE runtime and canonical spool required")
        runtime.store._assert_owners()
        self.runtime, self.spool = runtime, spool
        self.activation_directory = Path(activation_directory).resolve()
        self.phase_directory = Path(phase_directory).resolve()
        self.receipt_directory = Path(receipt_directory).resolve()
        if not callable(getattr(event_bus, "publish", None)):
            raise ValueError("explicit dashboard event bus required")
        self.dashboard = TradeLifecycleDashboardEventPublisherV2(event_bus_v2=event_bus)
        for path in (self.activation_directory, self.phase_directory, self.receipt_directory):
            path.mkdir(parents=True, exist_ok=True)

    def submit_signal(self, **request):
        result = self.runtime.lifecycle.submit_signal(**request)
        if result.get("accepted") is True:
            self.publish_admitted()
        return result

    def publish_admitted(self):
        store = self.runtime.store
        with store._durability.admission_barrier():
            store.receipt()  # The producer's mutation MUST already be committed.
            envelope = AuthenticatedAdmissionV3.read(store._native["admission_wire"].encode("ascii"))
            authority = self.runtime.lifecycle.native_admission_producer_v3.authority
            fields = authority.verify(envelope, now_us=utc_us(self.runtime.lifecycle.runtime_admission_v2.clock()),
                instrument=self.runtime.binding.instrument, runtime_generation=self.runtime.binding.runtime_generation,
                risk_version=store.admission["risk_version"])
            command = SimNativeCommandProtocolV2().build_submit_command(
                command_id=fields["command_id"], operation_id=fields["operation_id"],
                client_order_id=fields["client_order_id"], prepared_order={
                    "schema": "ARMS_SIM_COMMAND_V3", "admission_wire": b64encode(envelope.wire_bytes()).decode("ascii")})
            self.spool.write_command(command=command)
            if self.spool.read_command(command_id=fields["command_id"]) != command:
                raise ValueError("durable command/admission mismatch")
            marker = self.activation_directory / (fields["command_id"] + ".arm.json.consumed")
            if marker.exists():
                raise ValueError("activation already consumed; no automatic retry")
            # The entire admission is authenticated and is the single immutable
            # identity source; no unsigned price/permission field is interpreted.
            activation = {"schema": "ARMS_SIM_ACTIVATION_V3", "command_id": fields["command_id"],
                "activation_id": fields["activation_id"], "admission_digest": envelope.digest,
                "admission_wire": b64encode(envelope.wire_bytes()).decode("ascii")}
            self._create(self.activation_directory / (fields["command_id"] + ".arm.json"), activation)
            return command

    @staticmethod
    def _create(path, value):
        SimNativeCommandSpoolV2._create_once(path=path, payload=SimNativeCommandSpoolV2._canonical(value),
            collision_message="immutable native integration evidence collision",
            durability_error_message="native integration evidence sync failed")

    def reconcile(self):
        """Explicit evidence ingestion; no entry publication or broker calls."""
        store = self.runtime.store
        files = sorted(self.phase_directory.glob("*.state"))
        for number, path in enumerate(files, 1):
            if path.name != f"{number:08d}.state":
                raise ValueError("native phase gap")
            wire = path.read_bytes()
            phase = native_phase(wire, store._authority_key, store.admission_digest)
            store.binding.assert_claims(phase)
            if int(phase["generation"]) != number or phase.get("operation_id") != store.admission["operation_id"]:
                raise ValueError("native phase path/operation mismatch")
            # Re-verify old immutable evidence, but do not roll the checkpoint back.
            if number < store._native["generation"]:
                if any(store._native["executions"].get(k) != v for k, v in phase.items() if k.startswith("execution.")):
                    raise ValueError("historical native execution conflict")
                continue
            receipt = store.apply_phase(wire)
            self._create(self.receipt_directory / (f"{number:08d}.{receipt['checkpoint_digest']}.receipt.json"), receipt)
        store.publish_pending(self._publish_dashboard)

    def _publish_dashboard(self, *, event_id, event):
        store = self.runtime.store
        role, _, _ = execution_values(store._native["executions"][event["execution_id"]])
        entry = next(execution_values(value) for value in store._native["executions"].values()
                     if execution_values(value)[0] == "ENTRY")
        position = (store._position(entry[1], entry[2]) if role == "ENTRY"
                    else store.trade_lifecycle_service.portfolio_manager_v2.get_closed_positions()[0])
        trade = {**position, **event, "event_id": event_id, "order_role": role,
                 "position_id": store.position_id, "execution_domain": "SIM_NATIVE",
                 "portfolio": store.trade_lifecycle_service.portfolio_manager_v2.capture_risk_state()}
        publish = self.dashboard.publish_trade_opened if role == "ENTRY" else self.dashboard.publish_trade_closed
        result = publish(trade=trade)
        if result.get("published") is not True or result.get("listener_errors", 0):
            raise RuntimeError("dashboard delivery not acknowledged; outbox remains pending")
