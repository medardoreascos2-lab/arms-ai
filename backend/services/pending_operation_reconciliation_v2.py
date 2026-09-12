"""Explicit offline PAPER reconciliation. Never replay execution/accounting calls."""
from copy import deepcopy
from enum import Enum
import json
from pathlib import Path
from backend.services.recovery_semantic_validation_v2 import validate_semantic_state

from backend.connectors.paper_broker_connector_v2 import PaperBrokerConnectorV2
from backend.services.durable_execution_state_v2 import (
    atomic_write, canonical, checked_payload, evidence_path, seal, verify,
)


class ReconciliationStatus(str, Enum):
    CONFIRMED_NOT_EXECUTED = "CONFIRMED_NOT_EXECUTED"
    CONFIRMED_EXECUTED = "CONFIRMED_EXECUTED"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    AMBIGUOUS = "AMBIGUOUS"
    CORRUPT = "CORRUPT"


def operational(state):
    state = deepcopy(state)
    state.pop("captured_at", None)
    return state


class PendingOperationReconciliationV2:
    def __init__(self, store):
        self.store = store
        self._receipt = None

    @staticmethod
    def _signature(path):
        evidence = evidence_path(path)
        return (path, *(source.read_bytes() if source.is_file() else None for source in (
            path, evidence, path.with_suffix(path.suffix + ".tmp"),
            evidence.with_suffix(evidence.suffix + ".tmp"))))

    def _remember(self, path, report):
        self._receipt = (self._signature(path), operational(self.store.capture_state()), deepcopy(report))
        return report

    def _validate_transition(self, baseline, candidate):
        """Cross-check evidence, including closed identities and immutable fills."""
        before = baseline["execution_records"]
        after = candidate["execution_records"]
        if candidate["account_portfolio"] is None or after["journal"] is None:
            raise ValueError("Reconciliation requires canonical account, portfolio and journal.")
        paper = after["paper"]
        if not paper or not before["paper"]:
            raise ValueError("Missing PAPER evidence.")
        if paper["fills"][:len(before["paper"]["fills"])] != before["paper"]["fills"]:
            raise ValueError("Historical fills changed or disappeared.")
        for key, identity, terminal in (
                ("journal", "trade_id", "CLOSED"),
                ("protections", "protection_group_id", None),
                ("oco_groups", "oco_group_id", None)):
            rows = {row[identity]: row for row in after[key]}
            for row in before[key]:
                if row[identity] not in rows:
                    raise ValueError("Historical execution identity disappeared.")
                is_terminal = row["status"] == terminal if terminal else row["status"] != "ACTIVE"
                if is_terminal and rows[row[identity]] != row:
                    raise ValueError("Terminal execution record changed.")
        for key, row in before["paper"]["positions"].items():
            if key not in paper["positions"] or (row["status"] == "CLOSED" and paper["positions"][key] != row):
                raise ValueError("Closed PAPER position changed or disappeared.")
        risk_before = baseline["account_portfolio"]
        risk_after = candidate["account_portfolio"]
        if risk_before is None:
            raise ValueError("Missing baseline account evidence.")
        closed = {row["position_id"]: row for row in risk_after["closed_positions"]}
        if any(closed.get(row["position_id"]) != row for row in risk_before["closed_positions"]):
            raise ValueError("Closed portfolio position changed or reopened.")
        old_account = risk_before["account"]["state"]
        new_account = risk_after["account"]["state"]
        if (set(old_account["blocking_reasons"]) - set(new_account["blocking_reasons"])
                or old_account["trading_blocked"] and not new_account["trading_blocked"]):
            raise ValueError("Reconciliation cannot remove baseline risk blocks.")
        for key, order in before["paper"]["orders"].items():
            saved = paper["orders"].get(key)
            if saved is None or any(saved.get(field) != order.get(field) for field in (
                    "order_id", "client_order_id", "submitted_at", "symbol", "side", "quantity")):
                raise ValueError("Historical order identity changed or disappeared.")
        if any(paper["client_order_index"].get(key) != value
               for key, value in before["paper"]["client_order_index"].items()):
            raise ValueError("Historical client order identity changed.")
        if old_account["trading_day"] == new_account["trading_day"]:
            previous = risk_before["account"].get("daily_pnl_adjustments", [])
            current = risk_after["account"].get("daily_pnl_adjustments", [])
            if current[:len(previous)] != previous:
                raise ValueError("Historical daily risk adjustment changed or disappeared.")
        validate_semantic_state(candidate, point_value_for=self.store.trade_lifecycle_service.position_manager._resolve_point_value)

    def _classify(self, path, raw):
        pending = checked_payload(raw)
        metadata = pending.get("durability", {})
        if not isinstance(metadata, dict):
            raise ValueError("Invalid durability metadata.")
        if (metadata.get("version") != 1 or metadata.get("phase") != "PENDING"
                or type(metadata.get("generation")) is not int or metadata["generation"] < 1):
            raise ValueError("Invalid PENDING metadata.")
        operation_id = pending.pop("pending_operation", None)
        pending.pop("durability")
        baseline = self.store.validate_state(state=pending)
        if not operation_id or not evidence_path(path).is_file():
            return ReconciliationStatus.AMBIGUOUS, None, "No operation-bound evidence; legacy PENDING cannot be guessed."
        evidence = checked_payload(json.loads(evidence_path(path).read_text(encoding="utf-8")))
        if (evidence.get("version") != 1 or evidence.get("operation_id") != operation_id
                or evidence.get("generation") != metadata["generation"]
                or evidence.get("pending_checksum") != raw["checksum"]):
            return ReconciliationStatus.AMBIGUOUS, None, "Evidence does not identify this exact PENDING generation."
        if evidence_path(path).with_suffix(".json.tmp").exists():
            return ReconciliationStatus.AMBIGUOUS, None, "Interrupted evidence write; preserve all evidence."
        stage = evidence.get("stage")
        if stage not in {"PREPARED", "STARTED", "OBSERVED", "COMPLETED"}:
            raise ValueError("Unknown evidence stage.")
        try:
            candidate = self.store.validate_state(state=evidence["state"])
            self._validate_transition(baseline, candidate)
        except (ValueError, KeyError, TypeError) as exc:
            return ReconciliationStatus.AMBIGUOUS, None, str(exc)
        unchanged = operational(candidate) == operational(baseline)
        if stage == "PREPARED":
            if not unchanged:
                return ReconciliationStatus.AMBIGUOUS, None, "PREPARED contradicts the baseline."
            return ReconciliationStatus.CONFIRMED_NOT_EXECUTED, baseline, "Durable PREPARED precedes entry into the operation."
        if stage == "STARTED" or (stage == "OBSERVED" and unchanged):
            return ReconciliationStatus.AMBIGUOUS, None, "Execution started; absence of records is not proof of non-execution."
        outstanding = any(order["status"] not in PaperBrokerConnectorV2.VALID_FINAL_ORDER_STATUSES
                          for order in candidate["execution_records"]["paper"]["orders"].values())
        if stage == "OBSERVED" or outstanding:
            return ReconciliationStatus.PARTIALLY_EXECUTED, candidate, "Only the observed consistent prefix is proven; unresolved execution remains blocked."
        status = ReconciliationStatus.CONFIRMED_NOT_EXECUTED if unchanged else ReconciliationStatus.CONFIRMED_EXECUTED
        return status, candidate, "Complete, consistent operation result is durably linked to PENDING."

    def reconcile_from(self, *, file_path):
        """Use a fresh, offline runtime; call normal startup only after resolution.

        Unresolved results preserve PENDING. A crash in restoration is retried in
        a fresh process from the same evidence, never over a partially restored
        runtime. A resolved checkpoint is installed only after exact restoration.
        """
        path = Path(file_path).resolve()
        durability = self.store._durability
        with durability.lock:
            if self._receipt is not None:
                previous, state, report = self._receipt
                if self._signature(path) == previous and operational(self.store.capture_state()) == state:
                    return {**report, "idempotent": True}
                raise RuntimeError("Reconciliation evidence or operational state changed; use a fresh runtime.")
            if durability.failed or durability.enabled or durability.stopped:
                raise RuntimeError("Reconciliation requires a fresh offline runtime.")
            if not isinstance(self.store.trade_lifecycle_service.broker_connector_v2, PaperBrokerConnectorV2):
                durability.fail_closed()
                raise ValueError("Reconciliation is authorized only for PAPER.")
            try:
                durability.acquire(path)
                # Re-read under the exclusive writer lease.
                raw = json.loads(path.read_text(encoding="utf-8"))
                checked_payload(raw)
                metadata = raw.get("durability")
                if not isinstance(metadata, dict):
                    raise ValueError("Invalid durability metadata.")
                if metadata.get("phase") == "COMMITTED":
                    verify(raw)
                    receipt = raw.get("reconciliation")
                    if not isinstance(receipt, dict) or receipt.get("status") not in {
                            ReconciliationStatus.CONFIRMED_EXECUTED.value,
                            ReconciliationStatus.CONFIRMED_NOT_EXECUTED.value}:
                        raise ValueError("Checkpoint is not a reconciled PENDING operation.")
                    self.store.restore_from_file(file_path=path)
                    durability.enabled = True
                    report = {**receipt, "restored": True, "resolved": True, "idempotent": True}
                else:
                    status, candidate, reason = self._classify(path, raw)
                    resolved = status in {ReconciliationStatus.CONFIRMED_EXECUTED,
                                          ReconciliationStatus.CONFIRMED_NOT_EXECUTED}
                    report = {"status": status.value, "operation_id": raw.get("pending_operation"),
                              "pending_checksum": raw["checksum"], "generation": raw["durability"]["generation"],
                              "reason": reason, "restored": False, "resolved": resolved, "idempotent": False}
                    committed = None
                    if candidate is not None and resolved:
                        committed = seal({**candidate, "reconciliation": report},
                                         raw["durability"]["generation"], "COMMITTED")
                    temporary = path.with_suffix(path.suffix + ".tmp")
                    if temporary.exists():
                        # Only our exact resolution candidate may be resumed. Any
                        # other temporary write is additional unresolved evidence.
                        if committed is None or temporary.read_bytes() != canonical(committed) + b"\n":
                            report.update(status="AMBIGUOUS", resolved=False,
                                          reason="Unrecognized interrupted checkpoint write.")
                            candidate = None
                    if candidate is not None:
                        portfolio = self.store._risk_portfolio()
                        current_account = portfolio.account_state_manager_v2.get_state()
                        saved_account = candidate["account_portfolio"]["account"]["state"]
                        if (set(current_account["blocking_reasons"]) - set(saved_account["blocking_reasons"])
                                or current_account["trading_blocked"] and not saved_account["trading_blocked"]):
                            report.update(status="AMBIGUOUS", resolved=False,
                                          reason="Existing runtime risk blocks must be preserved.")
                            durability.fail_closed()
                            return self._remember(path, report)
                        self.store.restore_state(state=candidate)
                        if operational(self.store.capture_state()) != operational(candidate):
                            raise ValueError("Restored participants do not exactly match the evidence.")
                        report["restored"] = True
                        if report["resolved"]:
                            atomic_write(path, committed)
                            durability.generation = raw["durability"]["generation"]
                            self.store._remember_checkpoint(path, committed, durability.generation)
                            durability.enabled = True
                    if not report["resolved"]:
                        durability.fail_closed()
                return self._remember(path, report)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                durability.fail_closed()
                report = {"status": "CORRUPT", "resolved": False, "restored": False,
                          "idempotent": False, "reason": str(exc)}
                return self._remember(path, report)
            except BaseException:
                durability.fail_closed()
                raise
