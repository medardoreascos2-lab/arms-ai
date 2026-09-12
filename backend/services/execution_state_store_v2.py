from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from functools import wraps

from backend.services.recovery_semantic_validation_v2 import validate_semantic_state

from backend.connectors.paper_broker_connector_v2 import PaperBrokerConnectorV2
from backend.journal.trade_journal_v2 import TradeJournalEntry
from backend.services.durable_execution_state_v2 import (
    DurableExecutionStateV2, canonical, verify, state_locked, evidence_path,
)

from backend.execution.oco_manager_v2 import (
    OCOManagerV2,
)
from backend.execution.protective_order_registry_v2 import (
    ProtectiveOrderRegistryV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


def _fail_closed_restore(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except BaseException:
            self._durability.fail_closed()
            raise
    return call


class ExecutionStateStoreV2:
    """
    Captura, valida, persiste y restaura el estado
    activo del motor de ejecución.
    """

    SCHEMA_VERSION = "2.0"

    def __init__(
        self,
        *,
        trade_lifecycle_service: TradeLifecycleServiceV2,
        protective_order_registry: ProtectiveOrderRegistryV2,
        oco_manager: OCOManagerV2,
    ) -> None:
        self.trade_lifecycle_service = (
            trade_lifecycle_service
        )
        self.protective_order_registry = (
            protective_order_registry
        )
        self.oco_manager = oco_manager
        self._durability = DurableExecutionStateV2(self)
        self.account_identity = None
        self.account_namespace = None
        self._restored_state = None
        self._loaded_checkpoint = None
        self._checkpoint_versions = {}
        lifecycle = self.trade_lifecycle_service
        portfolio = self._risk_portfolio()
        for participant in (lifecycle, lifecycle.execution_manager, lifecycle.paper_execution_engine,
                            protective_order_registry, oco_manager,
                            lifecycle.broker_connector_v2 if isinstance(lifecycle.broker_connector_v2, PaperBrokerConnectorV2) else None,
                            lifecycle.trade_journal_v2, lifecycle.portfolio_manager_v2,
                            portfolio.account_state_manager_v2 if portfolio else None):
            if participant is not None:
                participant._durability = self._durability

    def require_namespace_path(self, path):
        if self.account_namespace is not None and Path(path).resolve() != self.account_namespace:
            raise ValueError("Cross-account durable namespace rejected.")

    def validate_account_identity(self, state):
        if self.account_identity is None:
            return
        identity = state.get("account_identity")
        if not isinstance(identity, dict) or set(identity) != set(self.account_identity):
            raise ValueError("Snapshot lacks canonical account identity.")
        for field in ("account_id", "profile_name"):
            if identity[field] != self.account_identity[field]:
                raise ValueError("Cross-account recovery rejected: " + field)
        generation = identity["runtime_generation"]
        if type(generation) is not int or not 1 <= generation <= self.account_identity["runtime_generation"]:
            raise ValueError("Invalid account runtime generation.")

    @staticmethod
    def _checkpoint_fingerprint(state):
        return hashlib.sha256(canonical(state)).hexdigest()

    def _remember_checkpoint(self, path, state, generation):
        self._checkpoint_versions[Path(path).resolve()] = (
            generation, self._checkpoint_fingerprint(state))

    def _accept_restored_checkpoint(self, normalized):
        # Reading a file must never grant authority to replace its operational state.
        # Adopt its version only after reconstructing that exact checkpoint.
        if self._loaded_checkpoint is not None:
            path, generation, fingerprint, state = self._loaded_checkpoint
            if state == normalized:
                self._checkpoint_versions[path] = (generation, fingerprint)
                self._durability.generation = max(self._durability.generation, generation)

    def _capture_records(self):
        lifecycle = self.trade_lifecycle_service
        broker = lifecycle.broker_connector_v2
        journal = lifecycle.trade_journal_v2
        trades = None
        if journal is not None:
            trades = [asdict(trade) for trade in journal.trades]
            for trade in trades:
                for key in ("created_at", "closed_at"):
                    if isinstance(trade[key], datetime):
                        trade[key] = trade[key].isoformat()
        return deepcopy({
            "journal": trades,
            "history": lifecycle.trade_history_manager.get_history(),
            "protections": self.protective_order_registry.list_protections(),
            "oco_groups": self.oco_manager.list_groups(),
            "paper": {
                "account_id": broker.account_id,
                "orders": broker._orders, "fills": broker._fills,
                "positions": broker._positions,
                "client_order_index": broker._client_order_index,
            } if isinstance(broker, PaperBrokerConnectorV2) else None,
        })

    def _validate_records(self, records, positions, risk_snapshot):
        lifecycle = self.trade_lifecycle_service
        if records is None:
            if self.account_identity is not None:
                raise ValueError("Coordinated recovery requires complete execution records.")
            if positions or (risk_snapshot and risk_snapshot["closed_positions"]):
                raise ValueError("Legacy snapshot lacks journal/execution records; reconciliation required.")
            records = {"journal": [], "history": [], "protections": [], "oco_groups": [],
                       "paper": {"account_id": lifecycle.broker_connector_v2.account_id,
                                 "orders": {}, "fills": [], "positions": {}, "client_order_index": {}}}
        if not isinstance(records, dict) or set(records) != {
                "journal", "history", "protections", "oco_groups", "paper"}:
            raise ValueError("Incomplete execution records.")
        for key, identity in (("history", "position_id"),
                              ("protections", "protection_group_id"),
                              ("oco_groups", "oco_group_id")):
            rows = records[key]
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise ValueError("Invalid execution records.")
            ids = [row.get(identity) for row in rows]
            if any(not value for value in ids) or len(ids) != len(set(ids)):
                raise ValueError("Duplicate or incomplete execution records.")
        trades = records["journal"]
        if (trades is None) != (lifecycle.trade_journal_v2 is None):
            raise ValueError("Journal configuration mismatch.")
        if trades is not None:
            if not isinstance(trades, list):
                raise ValueError("Invalid journal records.")
            for row in trades:
                self._journal_entry(row)  # Validate the complete dataclass before mutation.
            ids = [row["trade_id"] for row in trades]
            position_ids = [row["position_id"] for row in trades]
            if len(ids) != len(set(ids)) or len(position_ids) != len(set(position_ids)):
                raise ValueError("Duplicate journal records.")
            if risk_snapshot is not None:
                portfolio = risk_snapshot["open_positions"] + risk_snapshot["closed_positions"]
                by_position = {row["position_id"]: row for row in trades}
                if set(by_position) != {row["position_id"] for row in portfolio}:
                    raise ValueError("Journal/portfolio positions mismatch.")
                for position in portfolio:
                    row = by_position[position["position_id"]]
                    if row["status"] != position["status"] or row["pnl"] != position.get("realized_pnl", 0.0):
                        raise ValueError("Journal/portfolio accounting mismatch.")
                    if row["status"] == "OPEN" and row.get("remaining_quantity", row["contracts"]) not in (None, position["quantity"]):
                        raise ValueError("Journal remaining quantity mismatch.")
                history = {row["position_id"]: row for row in records["history"]}
                closed = {row["position_id"]: row for row in risk_snapshot["closed_positions"]}
                if set(history) != set(closed) or any(
                        history[key]["realized_pnl"] != closed[key]["realized_pnl"] for key in closed):
                    raise ValueError("Execution history/portfolio mismatch.")
        paper = records["paper"]
        broker = lifecycle.broker_connector_v2
        if paper is not None:
            if not isinstance(broker, PaperBrokerConnectorV2):
                raise ValueError("Cannot recover PAPER records into LIVE.")
            if not isinstance(paper, dict) or set(paper) != {
                    "account_id", "orders", "fills", "positions", "client_order_index"}:
                raise ValueError("Incomplete PAPER records.")
            if paper["account_id"] != broker.account_id:
                raise ValueError("PAPER account mismatch.")
            if any(not isinstance(paper[key], dict) for key in ("orders", "positions", "client_order_index")) or not isinstance(paper["fills"], list):
                raise ValueError("Invalid PAPER records.")
            if risk_snapshot is not None and trades is not None:
                active_broker_ids = {key for key, row in paper["positions"].items() if row["status"] == "OPEN"}
                if active_broker_ids != {row.get("broker_position_id") for row in positions}:
                    raise ValueError("PAPER exposure mismatch.")
                fill_ids = [fill["fill_id"] for fill in paper["fills"]]
                if len(fill_ids) != len(set(fill_ids)):
                    raise ValueError("Duplicate PAPER fills.")
                for fill in paper["fills"]:
                    if fill["order_id"] not in paper["orders"] or fill["execution_mode"] != "PAPER":
                        raise ValueError("Invalid PAPER fill reference.")
                for order in paper["orders"].values():
                    if order["execution_mode"] != "PAPER":
                        raise ValueError("PAPER/LIVE record mismatch.")
                    if order["status"] == "FILLED" and sum(
                            fill["order_id"] == order["order_id"] and fill.get("fill_type") != "PARTIAL_CLOSE"
                            for fill in paper["fills"]) != 1:
                        raise ValueError("Missing or duplicate PAPER entry fill.")
                for order_id in paper["client_order_index"].values():
                    if order_id not in paper["orders"]:
                        raise ValueError("PAPER idempotency index mismatch.")
                for position in positions:
                    saved = paper["positions"].get(position.get("broker_position_id"))
                    if (saved is None or saved["status"] != "OPEN"
                            or saved["quantity"] != position["quantity"]
                            or position.get("execution_mode") != "PAPER"):
                        raise ValueError("PAPER active position mismatch.")
        elif isinstance(broker, PaperBrokerConnectorV2):
            raise ValueError("Missing PAPER execution records.")
        return deepcopy(records)

    @staticmethod
    def _journal_entry(row):
        if not isinstance(row, dict) or set(row) != {field.name for field in fields(TradeJournalEntry)}:
            raise ValueError("Incomplete journal entry.")
        row = deepcopy(row)
        for key in ("created_at", "closed_at"):
            if row.get(key) is not None:
                row[key] = datetime.fromisoformat(row[key])
        return TradeJournalEntry(**row)

    def _restore_records(self, records):
        if records is None:
            return
        lifecycle = self.trade_lifecycle_service
        if lifecycle.trade_journal_v2 is not None:
            lifecycle.trade_journal_v2.trades = [self._journal_entry(row) for row in records["journal"]]
        history = lifecycle.trade_history_manager
        history._history = deepcopy(records["history"])
        history._position_ids = {row["position_id"] for row in history._history}
        self.protective_order_registry._protections = {
            row["protection_group_id"]: deepcopy(row) for row in records["protections"]}
        self.oco_manager._groups = {row["oco_group_id"]: deepcopy(row) for row in records["oco_groups"]}
        if records["paper"] is not None:
            broker = lifecycle.broker_connector_v2
            for key in ("orders", "fills", "positions", "client_order_index"):
                setattr(broker, "_" + key, deepcopy(records["paper"][key]))

    def _risk_portfolio(self):
        portfolio = self.trade_lifecycle_service.portfolio_manager_v2
        if portfolio is not None and portfolio.account_state_manager_v2 is not None:
            return portfolio
        return None

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _require_dict(
        value: object,
        *,
        field_name: str,
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(
                f"{field_name} debe ser un dict."
            )

        return dict(value)

    @staticmethod
    def _require_list(
        value: object,
        *,
        field_name: str,
    ) -> list[Any]:
        if not isinstance(value, list):
            raise ValueError(
                f"{field_name} debe ser una lista."
            )

        return list(value)

    @staticmethod
    def _required_text(
        record: dict[str, Any],
        *,
        field_name: str,
        record_name: str,
    ) -> str:
        value = str(
            record.get(field_name, "")
        ).strip()

        if not value:
            raise ValueError(
                f"{record_name}.{field_name} "
                "es obligatorio."
            )

        return value

    @state_locked
    def capture_state(
        self,
    ) -> dict[str, object]:
        active_positions = (
            self.trade_lifecycle_service
            .get_active_positions()
        )

        active_protections = (
            self.protective_order_registry
            .list_protections(
                status="ACTIVE",
            )
        )

        active_oco_groups = (
            self.oco_manager.list_groups(
                status="ACTIVE",
            )
        )

        portfolio = self._risk_portfolio()
        return {
            **({"account_identity": deepcopy(self.account_identity)} if self.account_identity else {}),
            "schema_version": self.SCHEMA_VERSION,
            "account_portfolio": portfolio.capture_risk_state() if portfolio is not None else None,
            "captured_at": self._utc_now(),
            "execution_records": self._capture_records(),
            "active_positions": [
                dict(position)
                for position in active_positions
            ],
            "protective_registry": {
                "protections": [
                    dict(protection)
                    for protection
                    in active_protections
                ],
            },
            "oco_manager": {
                "groups": [
                    dict(group)
                    for group
                    in active_oco_groups
                ],
            },
            "summary": {
                "active_positions": len(
                    active_positions
                ),
                "active_protections": len(
                    active_protections
                ),
                "active_oco_groups": len(
                    active_oco_groups
                ),
            },
        }

    def validate_state(
        self,
        *,
        state: dict[str, object],
    ) -> dict[str, object]:
        normalized_state = self._require_dict(
            state,
            field_name="state",
        )
        self.validate_account_identity(normalized_state)
        lifecycle = self.trade_lifecycle_service
        if (self._risk_portfolio() is None or lifecycle.trade_journal_v2 is None
                or not isinstance(lifecycle.broker_connector_v2, PaperBrokerConnectorV2)
                or lifecycle.protective_order_registry_v2 is not self.protective_order_registry
                or lifecycle.oco_manager_v2 is not self.oco_manager):
            raise ValueError("Recovery requires shared canonical PAPER/account/portfolio/journal/protection authorities.")
        # Memory recovery can also receive a persisted envelope. Never discard its fence.
        if "durability" in normalized_state or "checksum" in normalized_state:
            verify(normalized_state)


        schema_version = str(
            normalized_state.get(
                "schema_version",
                "",
            )
        ).strip()

        if schema_version != self.SCHEMA_VERSION:
            raise ValueError(
                "schema_version no compatible: "
                f"{schema_version!r}."
            )

        positions_raw = self._require_list(
            normalized_state.get(
                "active_positions",
            ),
            field_name="active_positions",
        )

        registry_state = self._require_dict(
            normalized_state.get(
                "protective_registry",
            ),
            field_name="protective_registry",
        )

        protections_raw = self._require_list(
            registry_state.get(
                "protections",
            ),
            field_name=(
                "protective_registry.protections"
            ),
        )

        oco_state = self._require_dict(
            normalized_state.get(
                "oco_manager",
            ),
            field_name="oco_manager",
        )

        groups_raw = self._require_list(
            oco_state.get("groups"),
            field_name="oco_manager.groups",
        )

        positions: list[dict[str, Any]] = []
        protections: list[dict[str, Any]] = []
        groups: list[dict[str, Any]] = []

        position_ids: set[str] = set()
        protection_ids: set[str] = set()
        oco_group_ids: set[str] = set()

        for index, raw_position in enumerate(
            positions_raw
        ):
            position = self._require_dict(
                raw_position,
                field_name=(
                    f"active_positions[{index}]"
                ),
            )

            position_id = self._required_text(
                position,
                field_name="position_id",
                record_name=(
                    f"active_positions[{index}]"
                ),
            )

            if position_id in position_ids:
                raise ValueError(
                    "position_id duplicado: "
                    f"{position_id}."
                )

            status = str(
                position.get("status", "")
            ).strip().upper()

            if status != "OPEN":
                raise ValueError(
                    "Las posiciones recuperables "
                    "deben tener status OPEN."
                )

            position_ids.add(position_id)
            positions.append(position)

        for index, raw_protection in enumerate(
            protections_raw
        ):
            protection = self._require_dict(
                raw_protection,
                field_name=(
                    "protective_registry."
                    f"protections[{index}]"
                ),
            )

            protection_group_id = (
                self._required_text(
                    protection,
                    field_name=(
                        "protection_group_id"
                    ),
                    record_name=(
                        "protective_registry."
                        f"protections[{index}]"
                    ),
                )
            )

            position_id = self._required_text(
                protection,
                field_name="position_id",
                record_name=(
                    "protective_registry."
                    f"protections[{index}]"
                ),
            )

            if (
                protection_group_id
                in protection_ids
            ):
                raise ValueError(
                    "protection_group_id "
                    "duplicado: "
                    f"{protection_group_id}."
                )

            if position_id not in position_ids:
                raise ValueError(
                    "La protección referencia una "
                    "posición inexistente: "
                    f"{position_id}."
                )

            status = str(
                protection.get("status", "")
            ).strip().upper()

            if status != "ACTIVE":
                raise ValueError(
                    "Las protecciones recuperables "
                    "deben tener status ACTIVE."
                )

            protection_ids.add(
                protection_group_id
            )
            protections.append(protection)

        for index, raw_group in enumerate(
            groups_raw
        ):
            group = self._require_dict(
                raw_group,
                field_name=(
                    f"oco_manager.groups[{index}]"
                ),
            )

            oco_group_id = self._required_text(
                group,
                field_name="oco_group_id",
                record_name=(
                    f"oco_manager.groups[{index}]"
                ),
            )

            position_id = self._required_text(
                group,
                field_name="position_id",
                record_name=(
                    f"oco_manager.groups[{index}]"
                ),
            )

            if oco_group_id in oco_group_ids:
                raise ValueError(
                    "oco_group_id duplicado: "
                    f"{oco_group_id}."
                )

            if position_id not in position_ids:
                raise ValueError(
                    "El grupo OCO referencia una "
                    "posición inexistente: "
                    f"{position_id}."
                )

            status = str(
                group.get("status", "")
            ).strip().upper()

            if status != "ACTIVE":
                raise ValueError(
                    "Los grupos OCO recuperables "
                    "deben tener status ACTIVE."
                )

            oco_group_ids.add(oco_group_id)
            groups.append(group)

        if len(protections) != len(positions) or len(groups) != len(positions):
            raise ValueError("Each active position requires exactly one protection and OCO group.")
        protections_by_position = {
            str(protection["position_id"]): (
                protection
            )
            for protection in protections
        }

        groups_by_position = {
            str(group["position_id"]): group
            for group in groups
        }

        for position in positions:
            position_id = str(
                position["position_id"]
            )

            protection = (
                protections_by_position.get(
                    position_id
                )
            )

            group = groups_by_position.get(
                position_id
            )

            if protection is None:
                raise ValueError(
                    "La posición no tiene una "
                    "protección activa: "
                    f"{position_id}."
                )

            if group is None:
                raise ValueError(
                    "La posición no tiene un grupo "
                    "OCO activo: "
                    f"{position_id}."
                )

            if str(
                position.get(
                    "protection_group_id",
                    "",
                )
            ).strip() != str(
                protection[
                    "protection_group_id"
                ]
            ):
                raise ValueError(
                    "protection_group_id "
                    "inconsistente para la posición "
                    f"{position_id}."
                )

            if str(
                position.get(
                    "oco_group_id",
                    "",
                )
            ).strip() != str(
                group["oco_group_id"]
            ):
                raise ValueError(
                    "oco_group_id inconsistente "
                    "para la posición "
                    f"{position_id}."
                )

            for position_key, protection_key in (
                    ("symbol", "symbol"), ("direction", "direction"),
                    ("quantity", "quantity"), ("entry_price", "entry_price"),
                    ("stop_loss", "stop_price"), ("take_profit", "take_profit_price")):
                if position.get(position_key) != protection.get(protection_key):
                    raise ValueError(f"Protection mismatch: {position_key}")

            for field_name in (
                "stop_order_id",
                "take_profit_order_id",
            ):
                position_order_id = str(
                    position.get(
                        field_name,
                        "",
                    )
                ).strip()

                protection_order_id = str(
                    protection.get(
                        field_name,
                        "",
                    )
                ).strip()

                group_order_id = str(
                    group.get(
                        field_name,
                        "",
                    )
                ).strip()

                if not (
                    position_order_id
                    == protection_order_id
                    == group_order_id
                ):
                    raise ValueError(
                        f"{field_name} inconsistente "
                        "para la posición "
                        f"{position_id}."
                    )

        portfolio = self._risk_portfolio()
        risk_snapshot = normalized_state.get("account_portfolio")
        if portfolio is not None:
            risk_snapshot = portfolio.validate_risk_state(snapshot=risk_snapshot)
            saved_open = {p["position_id"]: p for p in risk_snapshot["open_positions"]}
            if set(saved_open) != position_ids:
                raise ValueError("Active positions and risk portfolio do not match.")
            for position in positions:
                saved = saved_open[position["position_id"]]
                for key in ("symbol", "direction", "quantity", "entry_price", "current_price", "realized_pnl"):
                    if saved.get(key, 0.0) != position.get(key, 0.0):
                        raise ValueError(f"Active risk portfolio mismatch: {key}")
        elif risk_snapshot is not None:
            raise ValueError("Cannot discard an account risk snapshot.")

        records = self._validate_records(normalized_state.get("execution_records"), positions, risk_snapshot)
        if records is not None:
            if [r for r in records["protections"] if r["status"] == "ACTIVE"] != protections:
                raise ValueError("Active protection records mismatch.")
            if [r for r in records["oco_groups"] if r["status"] == "ACTIVE"] != groups:
                raise ValueError("Active OCO records mismatch.")
        validated = {
            **({"account_identity": deepcopy(normalized_state["account_identity"])} if self.account_identity else {}),
            "schema_version": self.SCHEMA_VERSION,
            "execution_records": records,
            "account_portfolio": risk_snapshot,
            "captured_at": (
                normalized_state.get(
                    "captured_at"
                )
            ),
            "active_positions": positions,
            "protective_registry": {
                "protections": protections,
            },
            "oco_manager": {
                "groups": groups,
            },
            "summary": {
                "active_positions": len(
                    positions
                ),
                "active_protections": len(
                    protections
                ),
                "active_oco_groups": len(
                    groups
                ),
            },
        }

        validate_semantic_state(validated, point_value_for=lifecycle.position_manager._resolve_point_value)
        return validated

    def verify_restored_state(self, *, state):
        expected = self.validate_state(state=state)
        actual = self.capture_state()
        self.validate_state(state=actual)
        actual["captured_at"] = expected["captured_at"]
        if self.account_identity is not None:
            # A newly published runtime can restore an older generation of the
            # same identity. Both identities were validated above; all financial
            # and execution participants must still match the checkpoint exactly.
            actual["account_identity"] = expected["account_identity"]
        if actual != expected:
            raise ValueError("Post-restore participants do not exactly match expected evidence.")
        return True

    def _ensure_empty_targets(
        self,
    ) -> None:
        if (
            self.trade_lifecycle_service
            .get_active_positions()
        ):
            raise ValueError(
                "No se puede restaurar sobre un "
                "servicio con posiciones activas."
            )

        if (
            self.protective_order_registry
            .list_protections()
        ):
            raise ValueError(
                "No se puede restaurar sobre un "
                "registro de protecciones no vacío."
            )

        if self.oco_manager.list_groups():
            raise ValueError(
                "No se puede restaurar sobre un "
                "administrador OCO no vacío."
            )

    @state_locked
    @_fail_closed_restore
    def restore_state(
        self,
        *,
        state: dict[str, object],
    ) -> dict[str, object]:
        normalized = self.validate_state(
            state=state,
        )

        if self._restored_state is not None:
            current = self.capture_state()
            current["captured_at"] = normalized["captured_at"]
            if current == normalized:
                self._accept_restored_checkpoint(normalized)
                return {"restored": True, "idempotent": True, **normalized["summary"]}
            raise ValueError("Cannot replay recovery over changed operational state.")
        self._ensure_empty_targets()
        records = self._capture_records()
        if (records["history"] or records["journal"]
                or (records["paper"] and any(records["paper"][key] for key in
                    ("orders", "fills", "positions", "client_order_index")))):
            raise ValueError("Cannot restore over existing execution records.")
        portfolio = self._risk_portfolio()
        if portfolio is not None:
            if portfolio.get_open_positions() or portfolio.get_closed_positions():
                raise ValueError("Cannot restore over existing portfolio evidence.")
            current_risk = portfolio.account_state_manager_v2.get_state()
            if any(current_risk[key] for key in ("realized_pnl", "unrealized_pnl", "open_positions", "closed_positions")):
                raise ValueError("Cannot restore over existing account execution evidence.")
            current_adjustments = portfolio.account_state_manager_v2.capture_state().get("daily_pnl_adjustments", [])
            if current_adjustments and current_adjustments != normalized["account_portfolio"]["account"].get("daily_pnl_adjustments", []):
                raise ValueError("Cannot overwrite existing risk block or daily adjustment evidence.")
            saved_risk = normalized["account_portfolio"]["account"]["state"]
            if (current_risk["trading_blocked"] and not saved_risk["trading_blocked"]
                    or set(current_risk["blocking_reasons"]) - set(saved_risk["blocking_reasons"])):
                raise ValueError("Recovery cannot remove an existing risk block.")
            portfolio.restore_risk_state(snapshot=normalized["account_portfolio"])

        positions = list(
            normalized["active_positions"]
        )

        protections = list(
            normalized[
                "protective_registry"
            ]["protections"]
        )

        groups = list(
            normalized[
                "oco_manager"
            ]["groups"]
        )

        for position in positions:
            self.trade_lifecycle_service\
                .restore_active_position(
                    position=dict(position),
                )

        for protection in protections:
            self.protective_order_registry\
                .create_protection(
                    position_id=str(
                        protection[
                            "position_id"
                        ]
                    ),
                    broker_position_id=(
                        str(
                            protection.get(
                                "broker_position_id",
                                "",
                            )
                        ).strip()
                        or None
                    ),
                    symbol=str(
                        protection["symbol"]
                    ),
                    direction=str(
                        protection["direction"]
                    ),
                    quantity=float(
                        protection["quantity"]
                    ),
                    entry_price=float(
                        protection["entry_price"]
                    ),
                    stop_price=float(
                        protection["stop_price"]
                    ),
                    take_profit_price=float(
                        protection[
                            "take_profit_price"
                        ]
                    ),
                    protection_group_id=str(
                        protection[
                            "protection_group_id"
                        ]
                    ),
                    stop_order_id=str(
                        protection[
                            "stop_order_id"
                        ]
                    ),
                    take_profit_order_id=str(
                        protection[
                            "take_profit_order_id"
                        ]
                    ),
                    metadata=dict(
                        protection.get(
                            "metadata",
                            {},
                        )
                    ),
                )

        for group in groups:
            self.oco_manager.create_group(
                position_id=str(
                    group["position_id"]
                ),
                stop_order_id=str(
                    group["stop_order_id"]
                ),
                take_profit_order_id=str(
                    group[
                        "take_profit_order_id"
                    ]
                ),
                oco_group_id=str(
                    group["oco_group_id"]
                ),
                metadata=dict(
                    group.get(
                        "metadata",
                        {},
                    )
                ),
            )

        self._restore_records(normalized.get("execution_records"))
        self.verify_restored_state(state=normalized)
        self._restored_state = deepcopy(normalized)
        self._accept_restored_checkpoint(normalized)
        return {
            "restored": True,
            "schema_version": self.SCHEMA_VERSION,
            "restored_at": self._utc_now(),
            "active_positions": len(positions),
            "active_protections": len(
                protections
            ),
            "active_oco_groups": len(groups),
        }

    def save_to_file(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        path = Path(file_path).resolve()
        with self._durability.lock:
            if self._durability.path is not None:
                if path != self._durability.path:
                    raise ValueError("Cannot redirect the active durable checkpoint.")
                state = self._durability.checkpoint()
            else:
                if self._durability.failed:
                    raise RuntimeError("Cannot overwrite failed recovery state.")
                was_stopped = self._durability.stopped
                self._durability.acquire(path)
                try:
                    evidence = evidence_path(path)
                    if not path.exists() and (evidence.exists() or evidence.with_suffix(evidence.suffix + ".tmp").exists()):
                        raise ValueError("Cannot overwrite orphaned operation evidence.")
                    if path.with_suffix(path.suffix + ".tmp").exists():
                        raise ValueError("Cannot overwrite an incomplete checkpoint.")
                    if path.exists():
                        disk_state = json.loads(path.read_text(encoding="utf-8"))
                        disk_version = (verify(disk_state), self._checkpoint_fingerprint(disk_state))
                        if disk_version != self._checkpoint_versions.get(path):
                            raise ValueError("Cannot overwrite a changed checkpoint without recovery.")
                    state = self._durability.checkpoint()
                finally:
                    self._durability.release()
                    # A manual snapshot does not stop a standalone service.
                    self._durability.stopped = was_stopped
        return {"saved": True, "file_path": str(path),
                "schema_version": self.SCHEMA_VERSION,
                "bytes_written": path.stat().st_size, "summary": dict(state["summary"])}

    @state_locked
    def load_from_file(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        path = Path(file_path)
        self.require_namespace_path(path)

        if path.with_suffix(path.suffix + ".tmp").exists():
            raise ValueError("Incomplete checkpoint file; reconciliation required.")
        if not path.is_file():
            raise FileNotFoundError(
                f"No existe el archivo: {path}"
            )

        try:
            raw_state = json.loads(
                path.read_text(
                    encoding="utf-8",
                )
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "El archivo de estado no contiene "
                "JSON válido."
            ) from exc

        generation = verify(raw_state)
        if self.account_identity is not None and generation < 1:
            raise ValueError("Coordinated recovery requires a durable generation.")
        state = self.validate_state(state=raw_state)
        self._loaded_checkpoint = (
            path.resolve(), generation, self._checkpoint_fingerprint(raw_state), deepcopy(state))
        return state

    def restore_from_file(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        state = self.load_from_file(
            file_path=file_path,
        )

        return self.restore_state(
            state=state,
        )
