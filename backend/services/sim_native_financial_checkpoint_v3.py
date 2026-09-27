"""Native SIM financial facts in the existing durable checkpoint boundary.

This is an explicit SIM schema, not a PAPER connector substitution. It never
submits, cancels, closes, or queries a broker. Native observations must already
be authenticated by the sole Account bridge. Deployment remains disabled.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from decimal import Decimal
import hashlib
import hmac
import json
from pathlib import Path

from backend.connectors.ninjatrader_sim_broker_connector_v2 import NinjaTraderSimBrokerConnectorV2
from backend.services.durable_execution_state_v2 import verify, state_locked
from backend.services.execution_state_store_v2 import ExecutionStateStoreV2
from backend.services.sim_admission_envelope_v3 import AuthenticatedAdmissionV3, validate as validate_admission
from backend.accounts.sim_native_account_v3 import SimNativeAccountV3


def native_phase(wire: bytes, key: bytes, admission_digest: str) -> dict[str, str]:
    """Authenticate a phase snapshot; this grants financial observation only."""
    if len(key) < 32 or len(wire) > 1_048_576:
        raise ValueError("invalid native phase authority/size")
    signature, payload = wire.split(b"\n", 1)
    expected = hmac.new(key, b"arms.native.phase.v3\0" + payload, hashlib.sha256).hexdigest().encode()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("unverifiable native phase")
    pairs = [line.split(b"\t") for line in payload.splitlines()]
    if any(len(pair) != 2 for pair in pairs):
        raise ValueError("invalid native phase")
    result = {k.decode("ascii"): base64.b64decode(v, validate=True).decode("utf-8") for k, v in pairs}
    encoded = b"".join(k.encode() + b"\t" + base64.b64encode(v.encode()) + b"\n"
                       for k, v in sorted(result.items()))
    if len(result) != len(pairs) or encoded != payload or result.get("admission_digest") != admission_digest:
        raise ValueError("native phase identity/canonical mismatch")
    if int(result["generation"]) < 1:
        raise ValueError("invalid phase generation")
    return result


def execution_values(value: str):
    role, quantity, price, order_id = value.split("|")
    price = Decimal(price)
    native_order_id = base64.b64decode(order_id, validate=True).decode("utf-8")
    if (role not in {"ENTRY", "PROTECTIVE_STOP", "PROFIT_TARGET", "RECOVERY_CLOSE"}
            or quantity != "1" or not price.is_finite() or price <= 0 or not native_order_id):
        raise ValueError("invalid native execution")
    return role, price, native_order_id


class NativeSimFinancialCheckpointV3(ExecutionStateStoreV2):
    """Single controlled operation, shared canonical financial participants.

    Adverse fills remain factual exposure even when approved levels are no
    longer valid. They are never passed through a PAPER fill/protection engine.
    """
    SCHEMA_VERSION = "SIM_NATIVE_FINANCIAL_V3"

    def __init__(self, *, trade_lifecycle_service, authority_key: bytes,
                 account_binding: SimNativeAccountV3, namespace_root, envelope=None):
        lifecycle = trade_lifecycle_service
        if (not isinstance(lifecycle.broker_connector_v2, NinjaTraderSimBrokerConnectorV2)
                or lifecycle.portfolio_manager_v2 is None or lifecycle.trade_journal_v2 is None):
            raise ValueError("explicit native SIM/account/portfolio/journal composition required")
        if type(account_binding) is not SimNativeAccountV3 or len(authority_key) < 32:
            raise ValueError("explicit native account/key authority required")
        self.binding = account_binding
        account_binding.manager()
        for owner in (lifecycle, lifecycle.broker_connector_v2, lifecycle.portfolio_manager_v2,
                      lifecycle.trade_journal_v2, lifecycle.portfolio_manager_v2.account_state_manager_v2):
            if getattr(owner, "sim_native_account_binding", None) is not account_binding:
                raise ValueError("cross-account financial participant rejected")
        self._owners = (lifecycle, lifecycle.broker_connector_v2, lifecycle.portfolio_manager_v2,
                        lifecycle.trade_journal_v2, lifecycle.portfolio_manager_v2.account_state_manager_v2)
        self._authority_key = authority_key
        self.admission, self.admission_digest = {}, ""
        if envelope is not None:
            self.admission = self._decode_admission(envelope.wire_bytes())
            self.admission_digest = envelope.digest
        self._native = {"admission_digest": self.admission_digest, "generation": 0,
                        "executions": {}, "outbox": {}, "delivered": [], "phase_digest": "",
                        "admission_wire": envelope.wire_bytes().decode("ascii") if envelope else ""}
        super().__init__(trade_lifecycle_service=lifecycle,
            protective_order_registry=lifecycle.protective_order_registry_v2,
            oco_manager=lifecycle.oco_manager_v2)
        self.account_identity = {"account_id": account_binding.backend_account_id,
            "profile_name": account_binding.risk_profile_id, "runtime_generation": account_binding.runtime_generation}
        self.account_namespace = account_binding.checkpoint_path(namespace_root)

    def _assert_owners(self):
        lifecycle = self.trade_lifecycle_service
        current = (lifecycle, lifecycle.broker_connector_v2, lifecycle.portfolio_manager_v2,
                   lifecycle.trade_journal_v2, lifecycle.portfolio_manager_v2.account_state_manager_v2)
        if any(owner is not original or getattr(owner, "sim_native_account_binding", None) is not self.binding
               for owner, original in zip(current, self._owners)):
            raise ValueError("cross-account financial participant replacement rejected")
        self.binding.manager()

    def _decode_admission(self, wire):
        envelope = AuthenticatedAdmissionV3.read(wire)
        # Authentication is checked independently of freshness: an expired entry
        # permission must not prevent recording a fill that actually occurred.
        payload = envelope.payload
        if (hashlib.sha256(payload).hexdigest() != envelope.digest
                or not hmac.compare_digest(envelope.authenticator, hmac.new(self._authority_key,
                    b"arms.native.admission.v3\0" + payload, hashlib.sha256).hexdigest())):
            raise ValueError("unverifiable financial admission")
        fields = envelope.fields()
        self.binding.assert_claims(fields)
        validate_admission(fields, now_us=int(fields["issued_us"]), instrument=self.binding.instrument,
            runtime_generation=self.binding.runtime_generation, risk_version=fields["risk_version"], account_binding=self.binding)
        return fields

    def record_admission(self, envelope):
        self.trade_lifecycle_service.runtime_admission_v2.require_execution_scope()
        if not self._durability.enabled or not self._durability.depth or self.admission_digest:
            raise ValueError("one durable controlled native admission required")
        self.admission = self._decode_admission(envelope.wire_bytes())
        self.admission_digest = envelope.digest
        self._native.update(admission_digest=envelope.digest, admission_wire=envelope.wire_bytes().decode("ascii"))

    def validate_account_identity(self, state):
        if state.get("account_identity") != self.account_identity:
            raise ValueError("cross-account/domain/generation checkpoint replay rejected")

    @property
    def position_id(self):
        return "native-" + self.admission_digest

    @state_locked
    def capture_state(self):
        self._assert_owners()
        state = super().capture_state()
        state["native_financial"] = deepcopy(self._native)
        state["sim_native_account"] = self.binding.claims()
        return state

    def validate_state(self, *, state):
        self._assert_owners()
        state = deepcopy(state)
        if "durability" in state or "checksum" in state:
            verify(state)
        state.pop("durability", None)
        state.pop("checksum", None)
        if state.get("schema_version") != self.SCHEMA_VERSION:
            raise ValueError("native financial schema required")
        self.validate_account_identity(state)
        if state.get("sim_native_account") != self.binding.claims():
            raise ValueError("native financial account/risk authority mismatch")
        native = state["native_financial"]
        if (set(native) != {"admission_digest", "generation", "executions", "outbox", "delivered", "phase_digest", "admission_wire"}
                or type(native["generation"]) is not int or native["generation"] < 0):
            raise ValueError("native financial identity mismatch")
        admission = self._decode_admission(native["admission_wire"].encode("ascii")) if native["admission_wire"] else {}
        admission_digest = AuthenticatedAdmissionV3.read(native["admission_wire"].encode("ascii")).digest if admission else ""
        if native["admission_digest"] != admission_digest or (self.admission_digest and self.admission_digest != admission_digest):
            raise ValueError("native financial admission mismatch")
        executions = native["executions"]
        if executions and not admission:
            raise ValueError("native financial facts require bound admission")
        values = [execution_values(value) for value in executions.values()]
        entries = [v for v in values if v[0] == "ENTRY"]
        exits = [v for v in values if v[0] != "ENTRY"]
        if len(entries) > 1 or len(exits) > len(entries):
            raise ValueError("contradictory native exposure")
        portfolio = self._risk_portfolio()
        risk = portfolio.validate_risk_state(snapshot=state["account_portfolio"])
        opened, closed = risk["open_positions"], risk["closed_positions"]
        if len(opened) != len(entries)-len(exits) or len(closed) != len(exits):
            raise ValueError("native execution/portfolio mismatch")
        if state["active_positions"] != opened:
            raise ValueError("native lifecycle/portfolio mismatch")
        for row in opened + closed:
            expected = self._position(entries[0][1], entries[0][2], admission=admission, admission_digest=admission_digest)
            for field in ("position_id", "symbol", "direction", "quantity", "entry_price",
                          "stop_loss", "take_profit", "point_value", "execution_mode", "order_id"):
                if row.get(field) != expected[field]:
                    raise ValueError("native position mismatch: " + field)
            if any(row.get(k) != v for k, v in self.binding.claims().items()):
                raise ValueError("native position account authority mismatch")
            pnl = self._pnl(entries[0][1], exits[0][1], admission=admission) if exits else 0.0
            if row.get("realized_pnl") != pnl or row.get("unrealized_pnl") != 0.0:
                raise ValueError("native financial effect mismatch")
            if exits and row.get("exit_price") != float(exits[0][1]):
                raise ValueError("native exit price mismatch")
        records = self._validate_records(state["execution_records"], opened, risk)
        if records["paper"] is not None or records["protections"] or records["oco_groups"]:
            raise ValueError("native checkpoint cannot invent PAPER/native protections")
        if state["protective_registry"] != {"protections": []} or state["oco_manager"] != {"groups": []}:
            raise ValueError("native protections require native evidence")
        expected_events = {self._event_id(k, admission_digest): {"execution_id": k, "admission_digest": admission_digest,
                            "backend_account_id": self.binding.backend_account_id, "execution_domain": "SIM_NATIVE"}
                           for k in executions}
        if native["outbox"] != expected_events or not set(native["delivered"]) <= set(expected_events):
            raise ValueError("financial dashboard identity mismatch")
        if len(native["delivered"]) != len(set(native["delivered"])):
            raise ValueError("duplicate financial publication identity")
        return state

    def _position(self, price, order_id, *, admission=None, admission_digest=None):
        admission = self.admission if admission is None else admission
        admission_digest = self.admission_digest if admission_digest is None else admission_digest
        return dict(**self.binding.claims(), position_id="native-" + admission_digest, order_id=order_id, execution_mode="SIM",
            symbol=admission["instrument"], direction="LONG" if admission["side"] == "BUY" else "SHORT",
            quantity=1, entry_price=float(price), current_price=float(price),
            stop_loss=float(admission["stop_price"]), take_profit=float(admission["target_price"]),
            point_value=float(admission["point_value"]), status="OPEN", realized_pnl=0.0,
            unrealized_pnl=0.0, total_pnl=0.0, native_protection_status="RECONCILIATION_REQUIRED")

    def _pnl(self, entry, exit, *, admission=None):
        admission = self.admission if admission is None else admission
        return float((exit-entry) * Decimal(admission["point_value"]) *
                     (1 if admission["side"] == "BUY" else -1))

    def _event_id(self, execution_id, admission_digest=None):
        admission_digest = self.admission_digest if admission_digest is None else admission_digest
        return hashlib.sha256((admission_digest + "\0" + execution_id).encode()).hexdigest()

    def _restore_validated(self, state):
        portfolio = self._risk_portfolio()
        portfolio._open_positions = {}
        portfolio._closed_positions = []
        portfolio.restore_risk_state(snapshot=state["account_portfolio"])
        self.trade_lifecycle_service._active_positions = {p["position_id"]: deepcopy(p) for p in state["active_positions"]}
        self._restore_records(state["execution_records"])
        self._native = deepcopy(state["native_financial"])
        self.admission = self._decode_admission(self._native["admission_wire"].encode("ascii")) if self._native["admission_wire"] else {}
        self.admission_digest = self._native["admission_digest"]

    @state_locked
    def rollback_state(self, *, state):
        previous_digest = self.admission_digest
        self.admission_digest = state["native_financial"]["admission_digest"]
        try:
            validated = self.validate_state(state=state)
        except BaseException:
            self.admission_digest = previous_digest
            raise
        self._restore_validated(validated)

    @state_locked
    def restore_state(self, *, state):
        normalized = self.validate_state(state=state)
        if self._native["executions"] or self._risk_portfolio().get_open_positions() or self._risk_portfolio().get_closed_positions():
            if self._restored_state == normalized:
                self.verify_restored_state(state=normalized)
                return {"restored": True}
            raise ValueError("cannot replace existing native financial state")
        self._restore_validated(normalized)
        self._restored_state = deepcopy(normalized)
        self._accept_restored_checkpoint(normalized)
        self.verify_restored_state(state=normalized)
        return {"restored": True}

    def start(self, path: Path | None = None):
        """Use the existing lease, PENDING fence, fsync, and committed checkpoint."""
        path = self.account_namespace if path is None else Path(path)
        self._durability.acquire(path)
        try:
            if path.with_suffix(path.suffix + ".tmp").exists():
                raise ValueError("incomplete native financial checkpoint")
            if path.exists():
                self.restore_from_file(file_path=path)
            elif path.with_suffix(path.suffix + ".evidence.json").exists():
                raise ValueError("orphan native financial operation requires reconciliation")
            self._durability.checkpoint()
            # This enables durable FINANCIAL mutations only. The inherited
            # PAPER-only enable() stays unchanged and grants no SIM execution.
            self._durability.enabled = True
        except BaseException:
            self._durability.fail_closed()
            self._durability.release()
            raise

    def apply_phase(self, wire: bytes):
        self._assert_owners()
        if not self._durability.enabled:
            raise RuntimeError("durable native financial checkpoint required")
        with self._durability.admission_barrier():
            phase = native_phase(wire, self._authority_key, self.admission_digest)
            self.binding.assert_claims(phase)
            if not self.admission or phase.get("operation_id") != self.admission["operation_id"]:
                raise ValueError("native financial operation identity mismatch")
            generation = int(phase["generation"])
            digest = hashlib.sha256(wire).hexdigest()
            if generation < self._native["generation"]:
                raise ValueError("native phase rollback")
            if generation == self._native["generation"]:
                if digest != self._native["phase_digest"]:
                    raise ValueError("conflicting native phase")
                return self.receipt()
            observations = {k: v for k, v in phase.items() if k.startswith("execution.")}
            for value in observations.values():
                role, price, order_id = execution_values(value)
                if (phase.get("order_id." + role) != order_id or phase.get("entry_filled") != "1"
                        or (role == "RECOVERY_CLOSE" and phase.get("flatten_intent") != "1")
                        or (role != "RECOVERY_CLOSE" and phase.get("submit." + role) != "1")
                        or (role != "ENTRY" and phase.get("exit_filled") != "1")):
                    raise ValueError("native execution/order/operation evidence mismatch")
            if any(observations.get(k) != v for k, v in self._native["executions"].items()):
                raise ValueError("native execution mutation/omission requires reconciliation")
            fresh = [(k, v, execution_values(v)) for k, v in observations.items() if k not in self._native["executions"]]
            fresh.sort(key=lambda item: item[2][0] != "ENTRY")
            with self._durability.mutation():
                lifecycle = self.trade_lifecycle_service
                portfolio, journal = self._risk_portfolio(), lifecycle.trade_journal_v2
                for execution_id, value, (role, price, order_id) in fresh:
                    if role == "ENTRY":
                        if portfolio.get_open_positions() or portfolio.get_closed_positions():
                            raise ValueError("second entry execution requires reconciliation")
                        position = self._position(price, order_id)
                        lifecycle._active_positions[self.position_id] = deepcopy(position)
                        portfolio.add_position(position=position)
                        journal.record_open_trade({**position, "trade_id": "journal-" + self.position_id})
                    else:
                        opened = portfolio.get_open_positions()
                        if len(opened) != 1:
                            raise ValueError("unmatched/duplicate native exit")
                        pnl = self._pnl(Decimal(str(opened[0]["entry_price"])), price)
                        closed = portfolio.close_position(position_id=self.position_id, exit_price=float(price), realized_pnl=pnl)["position"]
                        journal.close_trade(trade_id="journal-" + self.position_id, result=role, pnl=pnl,
                            exit_price=float(price), exit_reason=role, point_value=float(self.admission["point_value"]))
                        journal.trades[0].remaining_quantity = 0.0
                        lifecycle.trade_history_manager.record(position=closed)
                        lifecycle._active_positions.pop(self.position_id)
                    self._native["executions"][execution_id] = value
                    self._native["outbox"][self._event_id(execution_id)] = {
                        "execution_id": execution_id, "admission_digest": self.admission_digest,
                        "backend_account_id": self.binding.backend_account_id, "execution_domain": "SIM_NATIVE"}
                self._native.update(generation=generation, phase_digest=digest)
            return self.receipt()

    def receipt(self):
        self._assert_owners()
        # A receipt cannot precede or bypass a durable commit.
        disk = json.loads(self._durability.path.read_text(encoding="utf-8"))
        verify(disk)
        self.verify_restored_state(state=disk)
        if disk["native_financial"] != self._native:
            raise ValueError("uncommitted native financial state")
        evidence = "".join(k + "\t" + v + "\n" for k, v in sorted(self._native["executions"].items()))
        execution_digest = hashlib.sha256(evidence.encode()).hexdigest()
        payload = self.admission_digest + "\n" + execution_digest + "\n" + disk["checksum"] + "\n"
        return {"admission_digest": self.admission_digest, "executions_digest": execution_digest,
                "checkpoint_digest": disk["checksum"], "authenticator": hmac.new(self._authority_key,
                    b"arms.native.financial.v3\0" + payload.encode(), hashlib.sha256).hexdigest()}

    def publish_pending(self, publisher):
        """At-least-once delivery, stable event ID, no financial application here."""
        with self._durability.admission_barrier():
            self.receipt()
            for event_id, event in sorted(self._native["outbox"].items()):
                if event_id in self._native["delivered"]:
                    continue
                publisher(event_id=event_id, event=deepcopy(event))
                with self._durability.mutation():
                    self._native["delivered"].append(event_id)
