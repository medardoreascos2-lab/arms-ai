from __future__ import annotations

import json
from datetime import date
from datetime import time
from pathlib import Path

from backend.services.certified_market_calendar_v2 import (
    CertifiedCalendarSnapshotV2,
)
from backend.services.special_hours_snapshot_v2 import (
    CertifiedSpecialHoursSnapshotV2,
    CertifiedSpecialHoursWindowV2,
)


class CertifiedMarketHoursSnapshotLoaderV2:
    """
    Strict loader for versioned certified market-hours data.

    The loader does not infer, generate, or repair market-calendar
    information. Every accepted date and special-hours window must
    be explicitly present in the supplied JSON document.
    """

    def load_from_file(
        self,
        *,
        file_path: str | Path,
    ) -> tuple[
        CertifiedCalendarSnapshotV2,
        CertifiedSpecialHoursSnapshotV2,
    ]:
        path = self._normalize_path(file_path)

        if not path.is_file():
            raise FileNotFoundError(
                f"No existe el archivo certificado: {path}"
            )

        try:
            raw = json.loads(
                path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "El archivo certificado no contiene JSON válido."
            ) from exc

        return self.load_from_mapping(raw=raw)

    def load_from_mapping(
        self,
        *,
        raw: object,
    ) -> tuple[
        CertifiedCalendarSnapshotV2,
        CertifiedSpecialHoursSnapshotV2,
    ]:
        if not isinstance(raw, dict):
            raise TypeError(
                "El documento certificado debe ser un objeto JSON."
            )

        allowed_keys = {
            "covered_dates",
            "closed_dates",
            "special_hours",
        }

        unknown_keys = set(raw) - allowed_keys

        if unknown_keys:
            raise ValueError(
                "El documento certificado contiene campos "
                f"desconocidos: {sorted(unknown_keys)}"
            )

        missing_keys = allowed_keys - set(raw)

        if missing_keys:
            raise ValueError(
                "El documento certificado no contiene campos "
                f"obligatorios: {sorted(missing_keys)}"
            )

        covered_dates = self._parse_date_collection(
            field_name="covered_dates",
            raw_value=raw["covered_dates"],
        )

        closed_dates = self._parse_date_collection(
            field_name="closed_dates",
            raw_value=raw["closed_dates"],
        )

        special_hours = self._parse_special_hours(
            raw_value=raw["special_hours"],
        )

        calendar_snapshot = CertifiedCalendarSnapshotV2(
            covered_dates=covered_dates,
            closed_dates=closed_dates,
        )

        special_hours_snapshot = (
            CertifiedSpecialHoursSnapshotV2(
                windows=special_hours,
            )
        )

        return (
            calendar_snapshot,
            special_hours_snapshot,
        )

    @staticmethod
    def _normalize_path(
        file_path: str | Path,
    ) -> Path:
        if isinstance(file_path, str):
            if not file_path.strip():
                raise ValueError(
                    "file_path es obligatorio."
                )
        elif not isinstance(file_path, Path):
            raise TypeError(
                "file_path debe ser str o Path."
            )

        path = Path(file_path).expanduser()

        if path.exists() and path.is_dir():
            raise IsADirectoryError(
                f"La ruta certificada es un directorio: {path}"
            )

        return path

    @classmethod
    def _parse_date_collection(
        cls,
        *,
        field_name: str,
        raw_value: object,
    ) -> frozenset[date]:
        if not isinstance(raw_value, list):
            raise TypeError(
                f"{field_name} debe ser una lista."
            )

        parsed: list[date] = []

        for value in raw_value:
            parsed.append(
                cls._parse_date(
                    field_name=field_name,
                    raw_value=value,
                )
            )

        if len(parsed) != len(set(parsed)):
            raise ValueError(
                f"{field_name} contiene fechas duplicadas."
            )

        return frozenset(parsed)

    @classmethod
    def _parse_special_hours(
        cls,
        *,
        raw_value: object,
    ) -> tuple[CertifiedSpecialHoursWindowV2, ...]:
        if not isinstance(raw_value, list):
            raise TypeError(
                "special_hours debe ser una lista."
            )

        windows: list[
            CertifiedSpecialHoursWindowV2
        ] = []

        allowed_keys = {
            "local_date",
            "open_time",
            "close_time",
        }

        for index, item in enumerate(raw_value):
            if not isinstance(item, dict):
                raise TypeError(
                    "Cada elemento de special_hours "
                    "debe ser un objeto."
                )

            unknown_keys = set(item) - allowed_keys

            if unknown_keys:
                raise ValueError(
                    "special_hours contiene campos "
                    f"desconocidos en índice {index}: "
                    f"{sorted(unknown_keys)}"
                )

            missing_keys = allowed_keys - set(item)

            if missing_keys:
                raise ValueError(
                    "special_hours no contiene campos "
                    f"obligatorios en índice {index}: "
                    f"{sorted(missing_keys)}"
                )

            windows.append(
                CertifiedSpecialHoursWindowV2(
                    local_date=cls._parse_date(
                        field_name="local_date",
                        raw_value=item["local_date"],
                    ),
                    open_time=cls._parse_time(
                        field_name="open_time",
                        raw_value=item["open_time"],
                    ),
                    close_time=cls._parse_time(
                        field_name="close_time",
                        raw_value=item["close_time"],
                    ),
                )
            )

        return tuple(windows)

    @staticmethod
    def _parse_date(
        *,
        field_name: str,
        raw_value: object,
    ) -> date:
        if not isinstance(raw_value, str):
            raise TypeError(
                f"{field_name} debe contener fechas ISO string."
            )

        try:
            parsed = date.fromisoformat(raw_value)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} contiene una fecha ISO inválida: "
                f"{raw_value!r}"
            ) from exc

        return parsed

    @staticmethod
    def _parse_time(
        *,
        field_name: str,
        raw_value: object,
    ) -> time:
        if not isinstance(raw_value, str):
            raise TypeError(
                f"{field_name} debe ser hora ISO string."
            )

        try:
            parsed = time.fromisoformat(raw_value)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} contiene una hora ISO inválida: "
                f"{raw_value!r}"
            ) from exc

        if parsed.tzinfo is not None:
            raise ValueError(
                f"{field_name} debe ser hora local sin timezone."
            )

        return parsed
