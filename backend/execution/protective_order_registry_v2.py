from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4


class ProtectiveOrderRegistryV2:
    """
    Registro interno de protecciones asociadas
    a posiciones abiertas.

    Esta versión no envía órdenes al broker.
    Genera identificadores internos para Stop Loss
    y Take Profit, preparando la integración futura
    con OCOManagerV2 y brokers reales.
    """

    VALID_DIRECTIONS = {
        "LONG",
        "SHORT",
    }

    VALID_STATUSES = {
        "ACTIVE",
        "CANCELLED",
        "COMPLETED",
    }

    VALID_ORDER_STATUSES = {
        "ACTIVE",
        "FILLED",
        "CANCELLED",
    }

    def __init__(self) -> None:
        self._protections: dict[
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
    def _normalize_required_text(
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
    def _normalize_positive_float(
        value: object,
        *,
        field_name: str,
    ) -> float:
        normalized = float(value)

        if normalized <= 0:
            raise ValueError(
                f"{field_name} debe ser "
                "mayor que cero."
            )

        return normalized

    @staticmethod
    def _copy_protection(
        protection: dict[str, object],
    ) -> dict[str, object]:
        return deepcopy(protection)

    def create_protection(
        self,
        *,
        position_id: str,
        symbol: str,
        direction: str,
        quantity: float,
        entry_price: float,
        stop_price: float,
        take_profit_price: float,
        broker_position_id: str | None = None,
        protection_group_id: str | None = None,
        stop_order_id: str | None = None,
        take_profit_order_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        normalized_position_id = (
            self._normalize_required_text(
                position_id,
                field_name="position_id",
            )
        )

        normalized_symbol = (
            self._normalize_required_text(
                symbol,
                field_name="symbol",
            )
            .upper()
        )

        normalized_direction = (
            self._normalize_required_text(
                direction,
                field_name="direction",
            )
            .upper()
        )

        if (
            normalized_direction
            not in self.VALID_DIRECTIONS
        ):
            raise ValueError(
                "direction debe ser "
                "LONG o SHORT."
            )

        normalized_quantity = (
            self._normalize_positive_float(
                quantity,
                field_name="quantity",
            )
        )

        normalized_entry_price = (
            self._normalize_positive_float(
                entry_price,
                field_name="entry_price",
            )
        )

        normalized_stop_price = (
            self._normalize_positive_float(
                stop_price,
                field_name="stop_price",
            )
        )

        normalized_take_profit_price = (
            self._normalize_positive_float(
                take_profit_price,
                field_name=(
                    "take_profit_price"
                ),
            )
        )

        if normalized_direction == "LONG":
            if (
                normalized_stop_price
                >= normalized_entry_price
            ):
                raise ValueError(
                    "stop_price debe estar "
                    "por debajo de entry_price "
                    "para LONG."
                )

            if (
                normalized_take_profit_price
                <= normalized_entry_price
            ):
                raise ValueError(
                    "take_profit_price debe estar "
                    "por encima de entry_price "
                    "para LONG."
                )

        else:
            if (
                normalized_stop_price
                <= normalized_entry_price
            ):
                raise ValueError(
                    "stop_price debe estar "
                    "por encima de entry_price "
                    "para SHORT."
                )

            if (
                normalized_take_profit_price
                >= normalized_entry_price
            ):
                raise ValueError(
                    "take_profit_price debe estar "
                    "por debajo de entry_price "
                    "para SHORT."
                )

        existing = self.get_by_position(
            position_id=normalized_position_id,
            active_only=True,
        )

        if existing is not None:
            raise ValueError(
                "Ya existe una protección activa "
                "para esta posición."
            )

        normalized_group_id = str(
            protection_group_id or uuid4()
        ).strip()

        if not normalized_group_id:
            raise ValueError(
                "protection_group_id "
                "es obligatorio."
            )

        if (
            normalized_group_id
            in self._protections
        ):
            raise ValueError(
                "Ya existe una protección con "
                "ese protection_group_id."
            )

        normalized_stop_order_id = str(
            stop_order_id or uuid4()
        ).strip()

        normalized_take_profit_order_id = str(
            take_profit_order_id or uuid4()
        ).strip()

        if not normalized_stop_order_id:
            raise ValueError(
                "stop_order_id es obligatorio."
            )

        if not normalized_take_profit_order_id:
            raise ValueError(
                "take_profit_order_id "
                "es obligatorio."
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

        normalized_broker_position_id = None

        if broker_position_id is not None:
            normalized_broker_position_id = (
                self._normalize_required_text(
                    broker_position_id,
                    field_name=(
                        "broker_position_id"
                    ),
                )
            )

        created_at = self._utc_now()

        protection: dict[str, object] = {
            "protection_group_id": (
                normalized_group_id
            ),
            "position_id": (
                normalized_position_id
            ),
            "broker_position_id": (
                normalized_broker_position_id
            ),
            "symbol": normalized_symbol,
            "direction": normalized_direction,
            "quantity": normalized_quantity,
            "entry_price": (
                normalized_entry_price
            ),
            "stop_order_id": (
                normalized_stop_order_id
            ),
            "stop_price": (
                normalized_stop_price
            ),
            "stop_order_status": "ACTIVE",
            "take_profit_order_id": (
                normalized_take_profit_order_id
            ),
            "take_profit_price": (
                normalized_take_profit_price
            ),
            "take_profit_order_status": (
                "ACTIVE"
            ),
            "status": "ACTIVE",
            "triggered_order_id": None,
            "cancelled_order_id": None,
            "completion_reason": None,
            "metadata": dict(
                metadata or {}
            ),
            "created_at": created_at,
            "updated_at": created_at,
            "completed_at": None,
        }

        self._protections[
            normalized_group_id
        ] = protection

        return self._copy_protection(
            protection
        )

    def get_protection(
        self,
        *,
        protection_group_id: str,
    ) -> dict[str, object] | None:
        normalized_group_id = (
            self._normalize_required_text(
                protection_group_id,
                field_name=(
                    "protection_group_id"
                ),
            )
        )

        protection = self._protections.get(
            normalized_group_id
        )

        if protection is None:
            return None

        return self._copy_protection(
            protection
        )

    def get_by_position(
        self,
        *,
        position_id: str,
        active_only: bool = False,
    ) -> dict[str, object] | None:
        normalized_position_id = (
            self._normalize_required_text(
                position_id,
                field_name="position_id",
            )
        )

        for protection in (
            self._protections.values()
        ):
            if (
                protection["position_id"]
                != normalized_position_id
            ):
                continue

            if (
                active_only
                and protection["status"]
                != "ACTIVE"
            ):
                continue

            return self._copy_protection(
                protection
            )

        return None

    def list_protections(
        self,
        *,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        normalized_status = None

        if status is not None:
            normalized_status = str(
                status
            ).strip().upper()

            if (
                normalized_status
                not in self.VALID_STATUSES
            ):
                raise ValueError(
                    "status de protección "
                    "inválido."
                )

        protections = []

        for protection in (
            self._protections.values()
        ):
            if (
                normalized_status is not None
                and protection["status"]
                != normalized_status
            ):
                continue

            protections.append(
                self._copy_protection(
                    protection
                )
            )

        return protections

    def complete_protection(
        self,
        *,
        protection_group_id: str,
        triggered_order_id: str,
        reason: str,
    ) -> dict[str, object]:
        normalized_group_id = (
            self._normalize_required_text(
                protection_group_id,
                field_name=(
                    "protection_group_id"
                ),
            )
        )

        normalized_triggered_order_id = (
            self._normalize_required_text(
                triggered_order_id,
                field_name=(
                    "triggered_order_id"
                ),
            )
        )

        normalized_reason = (
            self._normalize_required_text(
                reason,
                field_name="reason",
            )
            .upper()
        )

        protection = self._protections.get(
            normalized_group_id
        )

        if protection is None:
            raise ValueError(
                "No existe la protección."
            )

        if protection["status"] != "ACTIVE":
            return self._copy_protection(
                protection
            )

        stop_order_id = str(
            protection["stop_order_id"]
        )

        take_profit_order_id = str(
            protection[
                "take_profit_order_id"
            ]
        )

        if normalized_triggered_order_id not in {
            stop_order_id,
            take_profit_order_id,
        }:
            raise ValueError(
                "triggered_order_id no pertenece "
                "a esta protección."
            )

        if (
            normalized_triggered_order_id
            == stop_order_id
        ):
            cancelled_order_id = (
                take_profit_order_id
            )
            protection[
                "stop_order_status"
            ] = "FILLED"
            protection[
                "take_profit_order_status"
            ] = "CANCELLED"
        else:
            cancelled_order_id = stop_order_id
            protection[
                "take_profit_order_status"
            ] = "FILLED"
            protection[
                "stop_order_status"
            ] = "CANCELLED"

        completed_at = self._utc_now()

        protection.update(
            {
                "status": "COMPLETED",
                "triggered_order_id": (
                    normalized_triggered_order_id
                ),
                "cancelled_order_id": (
                    cancelled_order_id
                ),
                "completion_reason": (
                    normalized_reason
                ),
                "updated_at": completed_at,
                "completed_at": completed_at,
            }
        )

        return self._copy_protection(
            protection
        )

    def cancel_protection(
        self,
        *,
        protection_group_id: str,
        reason: str = "MANUAL_CANCEL",
    ) -> dict[str, object]:
        normalized_group_id = (
            self._normalize_required_text(
                protection_group_id,
                field_name=(
                    "protection_group_id"
                ),
            )
        )

        normalized_reason = (
            self._normalize_required_text(
                reason,
                field_name="reason",
            )
            .upper()
        )

        protection = self._protections.get(
            normalized_group_id
        )

        if protection is None:
            raise ValueError(
                "No existe la protección."
            )

        if protection["status"] != "ACTIVE":
            return self._copy_protection(
                protection
            )

        completed_at = self._utc_now()

        protection.update(
            {
                "stop_order_status": (
                    "CANCELLED"
                ),
                "take_profit_order_status": (
                    "CANCELLED"
                ),
                "status": "CANCELLED",
                "completion_reason": (
                    normalized_reason
                ),
                "updated_at": completed_at,
                "completed_at": completed_at,
            }
        )

        return self._copy_protection(
            protection
        )

    def remove_protection(
        self,
        *,
        protection_group_id: str,
    ) -> bool:
        normalized_group_id = (
            self._normalize_required_text(
                protection_group_id,
                field_name=(
                    "protection_group_id"
                ),
            )
        )

        protection = self._protections.get(
            normalized_group_id
        )

        if protection is None:
            return False

        if protection["status"] == "ACTIVE":
            raise ValueError(
                "No se puede eliminar una "
                "protección activa."
            )

        del self._protections[
            normalized_group_id
        ]

        return True

    def snapshot(
        self,
    ) -> dict[str, object]:
        protections = self.list_protections()

        active_count = sum(
            1
            for protection in protections
            if protection["status"] == "ACTIVE"
        )

        completed_count = sum(
            1
            for protection in protections
            if (
                protection["status"]
                == "COMPLETED"
            )
        )

        cancelled_count = sum(
            1
            for protection in protections
            if (
                protection["status"]
                == "CANCELLED"
            )
        )

        return {
            "status": "READY",
            "total_protections": len(
                protections
            ),
            "active_protections": (
                active_count
            ),
            "completed_protections": (
                completed_count
            ),
            "cancelled_protections": (
                cancelled_count
            ),
            "protections": protections,
        }
