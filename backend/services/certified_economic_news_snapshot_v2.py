from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


def _require_aware_datetime(
    value: datetime,
    *,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(
            f"{field_name} must be a datetime"
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )

    return value


@dataclass(frozen=True)
class CertifiedEconomicNewsSnapshotV2:
    snapshot_version: str
    generated_at: datetime
    coverage_start: datetime
    coverage_end: datetime
    high_impact_events: frozenset[datetime]

    def __init__(
        self,
        *,
        snapshot_version: str,
        generated_at: datetime,
        coverage_start: datetime,
        coverage_end: datetime,
        high_impact_events: Iterable[datetime],
    ) -> None:
        if (
            not isinstance(snapshot_version, str)
            or not snapshot_version.strip()
        ):
            raise ValueError(
                "snapshot_version must be non-blank"
            )

        generated_at = _require_aware_datetime(
            generated_at,
            field_name="generated_at",
        )
        coverage_start = _require_aware_datetime(
            coverage_start,
            field_name="coverage_start",
        )
        coverage_end = _require_aware_datetime(
            coverage_end,
            field_name="coverage_end",
        )

        if coverage_start > coverage_end:
            raise ValueError(
                "coverage_start must not be after "
                "coverage_end"
            )

        events = frozenset(high_impact_events)

        for event in events:
            event = _require_aware_datetime(
                event,
                field_name="high_impact_event",
            )

            if not (
                coverage_start
                <= event
                <= coverage_end
            ):
                raise ValueError(
                    "high_impact_event must be "
                    "inside coverage"
                )

        object.__setattr__(
            self,
            "snapshot_version",
            snapshot_version,
        )
        object.__setattr__(
            self,
            "generated_at",
            generated_at,
        )
        object.__setattr__(
            self,
            "coverage_start",
            coverage_start,
        )
        object.__setattr__(
            self,
            "coverage_end",
            coverage_end,
        )
        object.__setattr__(
            self,
            "high_impact_events",
            events,
        )

    def is_timestamp_covered(
        self,
        timestamp: datetime,
    ) -> bool:
        timestamp = _require_aware_datetime(
            timestamp,
            field_name="timestamp",
        )

        return (
            self.coverage_start
            <= timestamp
            <= self.coverage_end
        )
