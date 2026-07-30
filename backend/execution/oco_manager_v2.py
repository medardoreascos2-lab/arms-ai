from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


class OCOManagerV2:
    """
    Administra grupos OCO (One Cancels the Other).

    Este componente mantiene únicamente el estado lógico de los
    grupos. La cancelación física de órdenes en un broker se
    integrará posteriormente mediante BrokerConnectorV2.
    """

    VALID_GROUP_STATUSES = {
        "ACTIVE",
        "COMPLETED",
        "CANCELLED",
    }

    TERMINAL_ORDER_STATUSES = {
        "FILLED",
        "CANCELLED",
    }

    def __init__(self) -> None:
        self._groups: dict[
            str,
            dict[str, object],
        ] = {}

    @staticmethod
    def _utc_now() -> str:
        return (
            datetime.now(timezone.utc)
            .isoformat()
        )

    @staticmethod
    def _normalize_required_id(
        value: object,
        *,
        field_name: str,
    ) -> str:
        normalized = str(
            value or ""
        ).strip()

        if not normalized:
            raise ValueError(
                f"{field_name} es obligatorio."
            )

        return normalized

    @staticmethod
    def _copy_group(
        group: dict[str, object],
    ) -> dict[str, object]:
        return dict(group)

    def create_group(
        self,
        *,
        position_id: str,
        stop_order_id: str,
        take_profit_order_id: str,
        oco_group_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        normalized_position_id = (
            self._normalize_required_id(
                position_id,
                field_name="position_id",
            )
        )

        normalized_stop_order_id = (
            self._normalize_required_id(
                stop_order_id,
                field_name="stop_order_id",
            )
        )

        normalized_take_profit_order_id = (
            self._normalize_required_id(
                take_profit_order_id,
                field_name=(
                    "take_profit_order_id"
                ),
            )
        )

        if (
            normalized_stop_order_id
            == normalized_take_profit_order_id
        ):
            raise ValueError(
                "stop_order_id y "
                "take_profit_order_id deben "
                "ser diferentes."
            )

        normalized_group_id = str(
            oco_group_id or uuid4()
        ).strip()

        if not normalized_group_id:
            raise ValueError(
                "oco_group_id es obligatorio."
            )

        if normalized_group_id in self._groups:
            raise ValueError(
                "Ya existe un grupo OCO con "
                "ese oco_group_id."
            )

        for existing_group in (
            self._groups.values()
        ):
            if (
                existing_group["status"]
                == "ACTIVE"
                and (
                    existing_group[
                        "position_id"
                    ]
                    == normalized_position_id
                )
            ):
                raise ValueError(
                    "Ya existe un grupo OCO "
                    "activo para esta posición."
                )

        created_at = self._utc_now()

        group: dict[str, object] = {
            "oco_group_id": (
                normalized_group_id
            ),
            "position_id": (
                normalized_position_id
            ),
            "stop_order_id": (
                normalized_stop_order_id
            ),
            "take_profit_order_id": (
                normalized_take_profit_order_id
            ),
            "stop_order_status": "ACTIVE",
            "take_profit_order_status": (
                "ACTIVE"
            ),
            "triggered_order_id": None,
            "cancelled_order_id": None,
            "status": "ACTIVE",
            "completion_reason": None,
            "metadata": dict(
                metadata or {}
            ),
            "created_at": created_at,
            "updated_at": created_at,
            "completed_at": None,
        }

        self._groups[
            normalized_group_id
        ] = group

        return self._copy_group(group)

    def get_group(
        self,
        *,
        oco_group_id: str,
    ) -> dict[str, object] | None:
        normalized_group_id = (
            self._normalize_required_id(
                oco_group_id,
                field_name="oco_group_id",
            )
        )

        group = self._groups.get(
            normalized_group_id
        )

        if group is None:
            return None

        return self._copy_group(group)

    def get_group_by_position(
        self,
        *,
        position_id: str,
        active_only: bool = False,
    ) -> dict[str, object] | None:
        normalized_position_id = (
            self._normalize_required_id(
                position_id,
                field_name="position_id",
            )
        )

        for group in self._groups.values():
            if (
                group["position_id"]
                != normalized_position_id
            ):
                continue

            if (
                active_only
                and group["status"] != "ACTIVE"
            ):
                continue

            return self._copy_group(group)

        return None

    def list_groups(
        self,
        *,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        normalized_status: str | None = None

        if status is not None:
            normalized_status = str(
                status
            ).strip().upper()

            if (
                normalized_status
                not in self.VALID_GROUP_STATUSES
            ):
                raise ValueError(
                    "status OCO inválido."
                )

        groups = []

        for group in self._groups.values():
            if (
                normalized_status is not None
                and group["status"]
                != normalized_status
            ):
                continue

            groups.append(
                self._copy_group(group)
            )

        return groups

    def cancel_remaining(
        self,
        *,
        oco_group_id: str,
        triggered_order_id: str,
        reason: str = "OCO_TRIGGERED",
    ) -> dict[str, object]:
        normalized_group_id = (
            self._normalize_required_id(
                oco_group_id,
                field_name="oco_group_id",
            )
        )

        normalized_triggered_order_id = (
            self._normalize_required_id(
                triggered_order_id,
                field_name=(
                    "triggered_order_id"
                ),
            )
        )

        normalized_reason = str(
            reason or "OCO_TRIGGERED"
        ).strip().upper()

        group = self._groups.get(
            normalized_group_id
        )

        if group is None:
            return {
                "completed": False,
                "idempotent": False,
                "status": "NOT_FOUND",
                "oco_group_id": (
                    normalized_group_id
                ),
                "triggered_order_id": (
                    normalized_triggered_order_id
                ),
                "cancelled_order_id": None,
                "group": None,
            }

        valid_order_ids = {
            str(group["stop_order_id"]),
            str(
                group[
                    "take_profit_order_id"
                ]
            ),
        }

        if (
            normalized_triggered_order_id
            not in valid_order_ids
        ):
            return {
                "completed": False,
                "idempotent": False,
                "status": (
                    "ORDER_NOT_IN_GROUP"
                ),
                "oco_group_id": (
                    normalized_group_id
                ),
                "triggered_order_id": (
                    normalized_triggered_order_id
                ),
                "cancelled_order_id": None,
                "group": (
                    self._copy_group(group)
                ),
            }

        if group["status"] == "COMPLETED":
            same_trigger = (
                group["triggered_order_id"]
                == normalized_triggered_order_id
            )

            return {
                "completed": bool(
                    same_trigger
                ),
                "idempotent": bool(
                    same_trigger
                ),
                "status": (
                    "ALREADY_COMPLETED"
                    if same_trigger
                    else "GROUP_ALREADY_RESOLVED"
                ),
                "oco_group_id": (
                    normalized_group_id
                ),
                "triggered_order_id": (
                    group[
                        "triggered_order_id"
                    ]
                ),
                "cancelled_order_id": (
                    group[
                        "cancelled_order_id"
                    ]
                ),
                "group": (
                    self._copy_group(group)
                ),
            }

        if group["status"] == "CANCELLED":
            return {
                "completed": False,
                "idempotent": False,
                "status": (
                    "GROUP_CANCELLED"
                ),
                "oco_group_id": (
                    normalized_group_id
                ),
                "triggered_order_id": None,
                "cancelled_order_id": None,
                "group": (
                    self._copy_group(group)
                ),
            }

        if (
            normalized_triggered_order_id
            == group["stop_order_id"]
        ):
            cancelled_order_id = str(
                group[
                    "take_profit_order_id"
                ]
            )
            group[
                "stop_order_status"
            ] = "FILLED"
            group[
                "take_profit_order_status"
            ] = "CANCELLED"
        else:
            cancelled_order_id = str(
                group["stop_order_id"]
            )
            group[
                "take_profit_order_status"
            ] = "FILLED"
            group[
                "stop_order_status"
            ] = "CANCELLED"

        completed_at = self._utc_now()

        group.update(
            {
                "triggered_order_id": (
                    normalized_triggered_order_id
                ),
                "cancelled_order_id": (
                    cancelled_order_id
                ),
                "status": "COMPLETED",
                "completion_reason": (
                    normalized_reason
                ),
                "updated_at": completed_at,
                "completed_at": completed_at,
            }
        )

        return {
            "completed": True,
            "idempotent": False,
            "status": "COMPLETED",
            "oco_group_id": (
                normalized_group_id
            ),
            "triggered_order_id": (
                normalized_triggered_order_id
            ),
            "cancelled_order_id": (
                cancelled_order_id
            ),
            "group": (
                self._copy_group(group)
            ),
        }

    def cancel_group(
        self,
        *,
        oco_group_id: str,
        reason: str = "MANUAL_CANCEL",
    ) -> dict[str, object]:
        normalized_group_id = (
            self._normalize_required_id(
                oco_group_id,
                field_name="oco_group_id",
            )
        )

        group = self._groups.get(
            normalized_group_id
        )

        if group is None:
            return {
                "cancelled": False,
                "idempotent": False,
                "status": "NOT_FOUND",
                "group": None,
            }

        if group["status"] == "CANCELLED":
            return {
                "cancelled": True,
                "idempotent": True,
                "status": (
                    "ALREADY_CANCELLED"
                ),
                "group": (
                    self._copy_group(group)
                ),
            }

        if group["status"] == "COMPLETED":
            return {
                "cancelled": False,
                "idempotent": False,
                "status": (
                    "GROUP_ALREADY_COMPLETED"
                ),
                "group": (
                    self._copy_group(group)
                ),
            }

        completed_at = self._utc_now()

        group.update(
            {
                "stop_order_status": (
                    "CANCELLED"
                ),
                "take_profit_order_status": (
                    "CANCELLED"
                ),
                "status": "CANCELLED",
                "completion_reason": str(
                    reason or "MANUAL_CANCEL"
                ).strip().upper(),
                "updated_at": completed_at,
                "completed_at": completed_at,
            }
        )

        return {
            "cancelled": True,
            "idempotent": False,
            "status": "CANCELLED",
            "group": (
                self._copy_group(group)
            ),
        }

    def remove_group(
        self,
        *,
        oco_group_id: str,
    ) -> dict[str, object]:
        normalized_group_id = (
            self._normalize_required_id(
                oco_group_id,
                field_name="oco_group_id",
            )
        )

        group = self._groups.get(
            normalized_group_id
        )

        if group is None:
            return {
                "removed": False,
                "status": "NOT_FOUND",
                "group": None,
            }

        if group["status"] == "ACTIVE":
            return {
                "removed": False,
                "status": (
                    "ACTIVE_GROUP_CANNOT_BE_REMOVED"
                ),
                "group": (
                    self._copy_group(group)
                ),
            }

        removed_group = self._groups.pop(
            normalized_group_id
        )

        return {
            "removed": True,
            "status": "REMOVED",
            "group": (
                self._copy_group(
                    removed_group
                )
            ),
        }

    def snapshot(
        self,
    ) -> dict[str, object]:
        groups = self.list_groups()

        return {
            "total_groups": len(groups),
            "active_groups": len(
                [
                    group
                    for group in groups
                    if group["status"]
                    == "ACTIVE"
                ]
            ),
            "completed_groups": len(
                [
                    group
                    for group in groups
                    if group["status"]
                    == "COMPLETED"
                ]
            ),
            "cancelled_groups": len(
                [
                    group
                    for group in groups
                    if group["status"]
                    == "CANCELLED"
                ]
            ),
            "groups": groups,
        }
