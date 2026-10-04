"""Provider-neutral Product notification store and local SQLite implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import re
import sqlite3
from typing import Protocol

from backend.product.notifications import NotificationStatus, ProductNotification


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_ALLOWED_ENVIRONMENTS = frozenset({"LOCAL_TEST_ONLY", "DEVELOPMENT"})


@dataclass(frozen=True)
class NotificationScope:
    tenant_id: str
    user_id: str

    def __post_init__(self) -> None:
        if _SAFE_ID.fullmatch(self.tenant_id) is None:
            raise ValueError("tenant_id must be a safe opaque identifier")
        if _SAFE_ID.fullmatch(self.user_id) is None:
            raise ValueError("user_id must be a safe opaque identifier")


class ProductNotificationStore(Protocol):
    def append(
        self, scope: NotificationScope, notification: ProductNotification,
        idempotency_key: str,
    ) -> ProductNotification: ...
    def list(self, scope: NotificationScope) -> tuple[ProductNotification, ...]: ...
    def get(
        self, scope: NotificationScope, notification_id: str,
    ) -> ProductNotification | None: ...
    def mark_read(
        self, scope: NotificationScope, notification_id: str, at: datetime,
    ) -> ProductNotification: ...
    def acknowledge(
        self, scope: NotificationScope, notification_id: str, at: datetime,
    ) -> ProductNotification: ...
    def snooze(
        self, scope: NotificationScope, notification_id: str,
        until: datetime, at: datetime,
    ) -> ProductNotification: ...
    def dismiss(
        self, scope: NotificationScope, notification_id: str, at: datetime,
    ) -> ProductNotification: ...


class LocalSqliteNotificationStore:
    """SQLite inbox for local test/development. It has no external transport."""

    def __init__(self, database_path: str, *, environment: str) -> None:
        if environment not in _ALLOWED_ENVIRONMENTS:
            raise ValueError("local notification store requires test/development environment")
        if not database_path:
            raise ValueError("database_path is required")
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS product_notifications (
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                notification_id TEXT NOT NULL,
                record_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, user_id, notification_id)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS product_notification_idempotency (
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                notification_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                PRIMARY KEY (tenant_id, user_id, idempotency_key)
            )
            """
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    @staticmethod
    def _require_time(value: datetime, name: str) -> None:
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() != timedelta(0)
        ):
            raise ValueError(f"{name} must be UTC")

    @staticmethod
    def _require_scope(
        scope: NotificationScope, notification: ProductNotification,
    ) -> None:
        if (
            notification.tenant_id != scope.tenant_id
            or notification.user_id != scope.user_id
        ):
            raise PermissionError("notification is outside tenant/user scope")

    def append(
        self, scope: NotificationScope, notification: ProductNotification,
        idempotency_key: str,
    ) -> ProductNotification:
        if not isinstance(scope, NotificationScope):
            raise TypeError("notification scope required")
        if not isinstance(notification, ProductNotification):
            raise TypeError("ProductNotification required")
        self._require_scope(scope, notification)
        if not isinstance(idempotency_key, str) or _SAFE_ID.fullmatch(idempotency_key) is None:
            raise ValueError("safe idempotency key required")
        payload = notification.model_dump_json()
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with self._connection:
            prior = self._connection.execute(
                """
                SELECT notification_id, payload_hash
                FROM product_notification_idempotency
                WHERE tenant_id = ? AND user_id = ? AND idempotency_key = ?
                """,
                (scope.tenant_id, scope.user_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if prior != (notification.notification_id, payload_hash):
                    raise ValueError("idempotency key reused for different notification")
                existing = self.get(scope, notification.notification_id)
                if existing is None:
                    raise RuntimeError("idempotency record is inconsistent")
                return existing
            self._connection.execute(
                """
                INSERT INTO product_notifications
                    (tenant_id, user_id, notification_id, record_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    scope.tenant_id, scope.user_id,
                    notification.notification_id, payload,
                ),
            )
            self._connection.execute(
                """
                INSERT INTO product_notification_idempotency
                    (tenant_id, user_id, idempotency_key, notification_id, payload_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    scope.tenant_id, scope.user_id, idempotency_key,
                    notification.notification_id, payload_hash,
                ),
            )
        return notification

    def list(self, scope: NotificationScope) -> tuple[ProductNotification, ...]:
        rows = self._connection.execute(
            """
            SELECT record_json FROM product_notifications
            WHERE tenant_id = ? AND user_id = ?
            ORDER BY rowid DESC
            """,
            (scope.tenant_id, scope.user_id),
        ).fetchall()
        return tuple(ProductNotification.model_validate_json(row[0]) for row in rows)

    def get(
        self, scope: NotificationScope, notification_id: str,
    ) -> ProductNotification | None:
        row = self._connection.execute(
            """
            SELECT record_json FROM product_notifications
            WHERE tenant_id = ? AND user_id = ? AND notification_id = ?
            """,
            (scope.tenant_id, scope.user_id, notification_id),
        ).fetchone()
        return None if row is None else ProductNotification.model_validate_json(row[0])

    def _required(
        self, scope: NotificationScope, notification_id: str,
    ) -> ProductNotification:
        item = self.get(scope, notification_id)
        if item is None:
            raise PermissionError("notification is unavailable in this scope")
        return item

    def _transition(
        self, scope: NotificationScope, notification_id: str,
        status: NotificationStatus, at: datetime, metadata: dict[str, object] | None = None,
    ) -> ProductNotification:
        self._require_time(at, "at")
        current = self._required(scope, notification_id)
        updated_metadata = dict(current.metadata)
        updated_metadata.update(metadata or {})
        updated = current.model_copy(update={
            "status": status,
            "metadata": updated_metadata,
        })
        with self._connection:
            self._connection.execute(
                """
                UPDATE product_notifications SET record_json = ?
                WHERE tenant_id = ? AND user_id = ? AND notification_id = ?
                """,
                (
                    updated.model_dump_json(), scope.tenant_id,
                    scope.user_id, notification_id,
                ),
            )
        return updated

    def mark_read(
        self, scope: NotificationScope, notification_id: str, at: datetime,
    ) -> ProductNotification:
        return self._transition(
            scope, notification_id, NotificationStatus.READ, at,
            {"read_at": at.isoformat()},
        )

    def acknowledge(
        self, scope: NotificationScope, notification_id: str, at: datetime,
    ) -> ProductNotification:
        return self._transition(
            scope, notification_id, NotificationStatus.ACKNOWLEDGED, at,
            {"acknowledged_at": at.isoformat()},
        )

    def snooze(
        self, scope: NotificationScope, notification_id: str,
        until: datetime, at: datetime,
    ) -> ProductNotification:
        self._require_time(until, "until")
        self._require_time(at, "at")
        if until <= at:
            raise ValueError("snooze must end after transition time")
        return self._transition(
            scope, notification_id, NotificationStatus.SNOOZED, at,
            {"snoozed_until": until.isoformat()},
        )

    def dismiss(
        self, scope: NotificationScope, notification_id: str, at: datetime,
    ) -> ProductNotification:
        current = self._required(scope, notification_id)
        if (
            current.requires_acknowledgement
            and current.status != NotificationStatus.ACKNOWLEDGED
        ):
            raise PermissionError("acknowledgement is required before dismissal")
        return self._transition(
            scope, notification_id, NotificationStatus.DISMISSED, at,
            {"dismissed_at": at.isoformat()},
        )
