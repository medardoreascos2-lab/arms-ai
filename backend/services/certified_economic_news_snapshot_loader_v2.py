from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from backend.services.certified_economic_news_snapshot_v2 import (
    CertifiedEconomicNewsSnapshotV2,
)


class CertifiedEconomicNewsSnapshotLoaderV2:
    """
    Strict loader for certified economic-news snapshots.

    The loader parses only explicit supplied data.

    It does not fetch, infer, repair, expand coverage,
    or create event windows.
    """

    _REQUIRED_FIELDS = frozenset(
        {
            "snapshot_version",
            "generated_at",
            "coverage_start",
            "coverage_end",
            "high_impact_events",
        }
    )

    def load_from_file(
        self,
        *,
        file_path: str | Path,
    ) -> CertifiedEconomicNewsSnapshotV2:
        path = self._normalize_path(
            file_path=file_path,
        )

        if not path.is_file():
            raise FileNotFoundError(
                f"No existe el archivo certificado: {path}"
            )

        try:
            raw = json.loads(
                path.read_text(
                    encoding="utf-8",
                )
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "El archivo certificado no contiene JSON válido."
            ) from exc

        return self.load_from_mapping(
            raw=raw,
        )

    def load_from_mapping(
        self,
        *,
        raw: object,
    ) -> CertifiedEconomicNewsSnapshotV2:
        if not isinstance(raw, dict):
            raise TypeError(
                "El documento certificado debe ser un objeto JSON."
            )

        unknown_fields = (
            set(raw)
            - self._REQUIRED_FIELDS
        )

        if unknown_fields:
            raise ValueError(
                "El documento certificado contiene campos "
                f"desconocidos: {sorted(unknown_fields)}"
            )

        missing_fields = (
            self._REQUIRED_FIELDS
            - set(raw)
        )

        if missing_fields:
            raise ValueError(
                "El documento certificado no contiene campos "
                f"obligatorios: {sorted(missing_fields)}"
            )

        snapshot_version = raw[
            "snapshot_version"
        ]

        if not isinstance(
            snapshot_version,
            str,
        ):
            raise TypeError(
                "snapshot_version debe ser string."
            )

        generated_at = self._parse_timestamp(
            field_name="generated_at",
            raw_value=raw["generated_at"],
        )

        coverage_start = self._parse_timestamp(
            field_name="coverage_start",
            raw_value=raw["coverage_start"],
        )

        coverage_end = self._parse_timestamp(
            field_name="coverage_end",
            raw_value=raw["coverage_end"],
        )

        high_impact_events = (
            self._parse_event_collection(
                raw_value=raw[
                    "high_impact_events"
                ],
            )
        )

        return CertifiedEconomicNewsSnapshotV2(
            snapshot_version=snapshot_version,
            generated_at=generated_at,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            high_impact_events=(
                high_impact_events
            ),
        )

    @staticmethod
    def _normalize_path(
        *,
        file_path: str | Path,
    ) -> Path:
        if isinstance(file_path, str):
            if not file_path.strip():
                raise ValueError(
                    "file_path es obligatorio."
                )
        elif not isinstance(
            file_path,
            Path,
        ):
            raise TypeError(
                "file_path debe ser str o Path."
            )

        path = Path(
            file_path
        ).expanduser()

        if (
            path.exists()
            and path.is_dir()
        ):
            raise IsADirectoryError(
                "La ruta certificada es un directorio: "
                f"{path}"
            )

        return path

    @classmethod
    def _parse_event_collection(
        cls,
        *,
        raw_value: object,
    ) -> frozenset[datetime]:
        if not isinstance(
            raw_value,
            list,
        ):
            raise TypeError(
                "high_impact_events debe ser una lista."
            )

        parsed = [
            cls._parse_timestamp(
                field_name=(
                    "high_impact_events"
                ),
                raw_value=value,
            )
            for value in raw_value
        ]

        if len(parsed) != len(set(parsed)):
            raise ValueError(
                "high_impact_events contiene "
                "timestamps duplicados."
            )

        return frozenset(parsed)

    @staticmethod
    def _parse_timestamp(
        *,
        field_name: str,
        raw_value: object,
    ) -> datetime:
        if not isinstance(
            raw_value,
            str,
        ):
            raise TypeError(
                f"{field_name} debe ser timestamp ISO string."
            )

        try:
            parsed = datetime.fromisoformat(
                raw_value,
            )
        except ValueError as exc:
            raise ValueError(
                f"{field_name} contiene timestamp ISO inválido: "
                f"{raw_value!r}"
            ) from exc

        if (
            parsed.tzinfo is None
            or parsed.utcoffset() is None
        ):
            raise ValueError(
                f"{field_name} debe incluir timezone."
            )

        return parsed
