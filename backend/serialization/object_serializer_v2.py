from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ObjectSerializerV2:
    """
    Convierte objetos de dominio en estructuras
    compatibles con JSON.
    """

    def serialize(
        self,
        value: Any,
    ) -> Any:

        if value is None:
            return None

        if isinstance(
            value,
            (
                bool,
                int,
                float,
                str,
            ),
        ):
            return value

        if isinstance(
            value,
            Enum,
        ):
            return self.serialize(
                value.value
            )

        if isinstance(
            value,
            (
                datetime,
                date,
            ),
        ):
            return value.isoformat()

        if isinstance(
            value,
            Path,
        ):
            return str(
                value
            )

        if isinstance(
            value,
            dict,
        ):
            return {
                str(key): self.serialize(
                    item
                )
                for key, item
                in value.items()
            }

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
                frozenset,
            ),
        ):
            return [
                self.serialize(
                    item
                )
                for item in value
            ]

        if is_dataclass(value):
            return {
                field.name: self.serialize(
                    getattr(
                        value,
                        field.name,
                    )
                )
                for field in fields(value)
            }

        to_dict = getattr(
            value,
            "to_dict",
            None,
        )

        if callable(to_dict):
            return self.serialize(
                to_dict()
            )

        raise TypeError(
            "El objeto no es serializable."
        )
