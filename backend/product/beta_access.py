"""Closed-beta access records with strict tenant and user scope."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
import sqlite3

from pydantic import BaseModel, ConfigDict, Field, field_validator


_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class BetaAccessStatus(str, Enum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class BetaAccessRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    access_id: str = Field(pattern=_SAFE_ID)
    tenant_id: str = Field(pattern=_SAFE_ID)
    user_id: str = Field(pattern=_SAFE_ID)
    status: BetaAccessStatus
    invited_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
    version: int = Field(ge=1)

    @field_validator("invited_at", "updated_at", "expires_at")
    @classmethod
    def timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() != timedelta(0)):
            raise ValueError("beta access timestamps must be UTC")
        return value


class LocalSqliteBetaAccessStore:
    """Local test/development projection. It performs no authentication mutation."""

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS beta_access (
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                version INTEGER NOT NULL,
                PRIMARY KEY (tenant_id, user_id)
            )
        """)

    def get(self, tenant_id: str, user_id: str) -> BetaAccessRecord | None:
        row = self._db.execute(
            "SELECT payload FROM beta_access WHERE tenant_id = ? AND user_id = ?",
            (tenant_id, user_id),
        ).fetchone()
        return BetaAccessRecord.model_validate_json(row[0]) if row else None

    def save(self, record: BetaAccessRecord, *, expected_version: int | None = None) -> None:
        current = self.get(record.tenant_id, record.user_id)
        if current is None:
            if expected_version is not None:
                raise ValueError("beta access record does not exist")
            self._db.execute(
                "INSERT INTO beta_access VALUES (?, ?, ?, ?)",
                (record.tenant_id, record.user_id, record.model_dump_json(), record.version),
            )
        else:
            if expected_version != current.version or record.version != current.version + 1:
                raise ValueError("beta access version conflict")
            self._db.execute(
                "UPDATE beta_access SET payload = ?, version = ? WHERE tenant_id = ? AND user_id = ?",
                (record.model_dump_json(), record.version, record.tenant_id, record.user_id),
            )
        self._db.commit()

    def list_records(self, tenant_id: str) -> tuple[BetaAccessRecord, ...]:
        rows = self._db.execute(
            "SELECT payload FROM beta_access WHERE tenant_id = ? ORDER BY user_id",
            (tenant_id,),
        ).fetchall()
        return tuple(BetaAccessRecord.model_validate_json(row[0]) for row in rows)