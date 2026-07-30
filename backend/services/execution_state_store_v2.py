from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.execution.oco_manager_v2 import (
    OCOManagerV2,
)
from backend.execution.protective_order_registry_v2 import (
    ProtectiveOrderRegistryV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


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

        return {
            "schema_version": self.SCHEMA_VERSION,
            "captured_at": self._utc_now(),
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

        return {
            "schema_version": self.SCHEMA_VERSION,
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

    def restore_state(
        self,
        *,
        state: dict[str, object],
    ) -> dict[str, object]:
        normalized = self.validate_state(
            state=state,
        )

        self._ensure_empty_targets()

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
        path = Path(file_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        state = self.capture_state()

        temporary_path = path.with_suffix(
            path.suffix + ".tmp"
        )

        serialized = json.dumps(
            state,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

        temporary_path.write_text(
            serialized + "\n",
            encoding="utf-8",
        )

        temporary_path.replace(path)

        return {
            "saved": True,
            "file_path": str(path),
            "schema_version": (
                self.SCHEMA_VERSION
            ),
            "bytes_written": (
                path.stat().st_size
            ),
            "summary": dict(
                state["summary"]
            ),
        }

    def load_from_file(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        path = Path(file_path)

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

        return self.validate_state(
            state=raw_state,
        )

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
