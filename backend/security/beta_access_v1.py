"""Fail-closed identity, password, session, and beta-access storage."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac, sha256
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
from threading import RLock
from typing import Any
from uuid import uuid4


PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
DEFAULT_BETA_DAYS = 30
DEFAULT_SESSION_HOURS = 12
ALLOWED_ROLES = frozenset({"admin", "beta_user", "disabled"})


class BetaAuthenticationError(Exception):
    """Raised when credentials or a session cannot be authenticated."""


class BetaAccessDeniedError(Exception):
    """Raised with a stable fail-closed access reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class BetaUserIdentity:
    user_id: str
    email: str
    role: str
    status: str
    beta_start_at: str | None
    beta_expires_at: str | None
    created_at: str
    last_login_at: str | None

    def to_public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BetaSession:
    token: str
    csrf_token: str
    expires_at: str
    user: BetaUserIdentity


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError("timestamp must be a datetime or ISO string")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _as_utc(value).isoformat()


def hash_beta_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    if len(password) > 1024:
        raise ValueError("password is too long")
    salt = secrets.token_bytes(16)
    digest = pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return "$".join(
        (PASSWORD_ALGORITHM, str(PASSWORD_ITERATIONS), salt.hex(), digest.hex())
    )


def verify_beta_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt_hex, digest_hex = encoded.split("$")
        iterations = int(iterations_text)
        if algorithm != PASSWORD_ALGORITHM or iterations < PASSWORD_ITERATIONS:
            return False
        actual = pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iterations
        )
        expected = bytes.fromhex(digest_hex)
    except (AttributeError, TypeError, ValueError):
        return False
    return hmac.compare_digest(actual, expected)


_DUMMY_PASSWORD_HASH = hash_beta_password("ARMS-beta-dummy-password-only")


class BetaUserStoreV1:
    """Small isolated SQLite authority for Beta Dashboard V1 access only."""

    def __init__(
        self,
        database_path: str | Path = ":memory:",
        *,
        cookie_secure: bool = False,
        now_provider=_utc_now,
    ) -> None:
        if database_path != ":memory:":
            path = Path(database_path).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            database_path = str(path)
        self.cookie_secure = bool(cookie_secure)
        self._now = now_provider
        self._lock = RLock()
        self._connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._initialize_schema()
        self._dummy_password_hash = _DUMMY_PASSWORD_HASH

    @classmethod
    def from_environment(cls) -> "BetaUserStoreV1":
        database_path = os.getenv("ARMS_BETA_DATABASE_PATH", ":memory:").strip()
        secure_raw = os.getenv("ARMS_BETA_COOKIE_SECURE", "false").strip().lower()
        if secure_raw not in {"true", "false", "1", "0", "yes", "no"}:
            raise ValueError("ARMS_BETA_COOKIE_SECURE must be true or false")
        store = cls(
            database_path or ":memory:",
            cookie_secure=secure_raw in {"true", "1", "yes"},
        )
        email = os.getenv("ARMS_BETA_ADMIN_EMAIL")
        password = os.getenv("ARMS_BETA_ADMIN_PASSWORD")
        if bool(email) != bool(password):
            raise ValueError(
                "ARMS_BETA_ADMIN_EMAIL and ARMS_BETA_ADMIN_PASSWORD must be set together"
            )
        if email and password:
            store.ensure_bootstrap_admin(email=email, password=password)
        return store

    def _initialize_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS beta_users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'beta_user', 'disabled')),
                    status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
                    beta_start_at TEXT,
                    beta_expires_at TEXT,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                );
                CREATE TABLE IF NOT EXISTS beta_sessions (
                    session_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES beta_users(user_id) ON DELETE CASCADE,
                    csrf_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_beta_sessions_user
                    ON beta_sessions(user_id);
                """
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def ensure_bootstrap_admin(self, *, email: str, password: str) -> BetaUserIdentity:
        normalized = self._normalize_email(email)
        existing = self._find_user_row_by_email(normalized)
        if existing is not None:
            identity = self._identity(existing)
            if identity.role != "admin":
                raise BetaAccessDeniedError("bootstrap_email_not_admin")
            return identity
        return self.create_user(email=normalized, password=password, role="admin")

    def create_user(
        self,
        *,
        email: str,
        password: str,
        role: str = "beta_user",
        beta_days: int = DEFAULT_BETA_DAYS,
        now: datetime | None = None,
    ) -> BetaUserIdentity:
        normalized_email = self._normalize_email(email)
        normalized_role = str(role).strip().lower()
        if normalized_role not in ALLOWED_ROLES:
            raise ValueError("invalid beta role")
        if not isinstance(beta_days, int) or not 1 <= beta_days <= 3650:
            raise ValueError("beta_days must be between 1 and 3650")
        timestamp = _as_utc(now or self._now())
        beta_start = None
        beta_expires = None
        if normalized_role != "admin":
            beta_start = _iso(timestamp)
            beta_expires = _iso(timestamp + timedelta(days=beta_days))
        status = "disabled" if normalized_role == "disabled" else "active"
        user_id = str(uuid4())
        password_hash = hash_beta_password(password)
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    """
                    INSERT INTO beta_users (
                        user_id, email, password_hash, role, status,
                        beta_start_at, beta_expires_at, created_at, last_login_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        user_id,
                        normalized_email,
                        password_hash,
                        normalized_role,
                        status,
                        beta_start,
                        beta_expires,
                        _iso(timestamp),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("email already exists") from exc
        return self.get_user(user_id)

    def authenticate(
        self,
        *,
        email: str,
        password: str,
        now: datetime | None = None,
    ) -> BetaSession:
        normalized_email = self._normalize_email(email)
        row = self._find_user_row_by_email(normalized_email)
        encoded = row["password_hash"] if row is not None else self._dummy_password_hash
        if not verify_beta_password(password, encoded) or row is None:
            raise BetaAuthenticationError("invalid_credentials")
        timestamp = _as_utc(now or self._now())
        identity = self._identity(row)
        self._require_access(identity, timestamp)
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        session_expires = timestamp + timedelta(hours=DEFAULT_SESSION_HOURS)
        if identity.role != "admin" and identity.beta_expires_at:
            session_expires = min(session_expires, _as_utc(identity.beta_expires_at))
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE beta_users SET last_login_at = ? WHERE user_id = ?",
                (_iso(timestamp), identity.user_id),
            )
            self._connection.execute(
                """
                INSERT INTO beta_sessions (
                    session_hash, user_id, csrf_hash, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self._digest(token),
                    identity.user_id,
                    self._digest(csrf_token),
                    _iso(timestamp),
                    _iso(session_expires),
                ),
            )
        return BetaSession(
            token=token,
            csrf_token=csrf_token,
            expires_at=_iso(session_expires),
            user=self.get_user(identity.user_id),
        )

    def resolve_session(
        self,
        token: str | None,
        *,
        now: datetime | None = None,
    ) -> BetaUserIdentity:
        if not isinstance(token, str) or not token:
            raise BetaAuthenticationError("authentication_required")
        timestamp = _as_utc(now or self._now())
        with self._lock:
            row = self._connection.execute(
                """
                SELECT u.*, s.expires_at AS session_expires_at
                FROM beta_sessions s
                JOIN beta_users u ON u.user_id = s.user_id
                WHERE s.session_hash = ?
                """,
                (self._digest(token),),
            ).fetchone()
        if row is None:
            raise BetaAuthenticationError("authentication_required")
        if _as_utc(row["session_expires_at"]) <= timestamp:
            self._delete_session(token)
            raise BetaAuthenticationError("session_expired")
        identity = self._identity(row)
        self._require_access(identity, timestamp)
        return identity

    def rotate_csrf(self, token: str) -> str:
        self.resolve_session(token)
        csrf_token = secrets.token_urlsafe(32)
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE beta_sessions SET csrf_hash = ? WHERE session_hash = ?",
                (self._digest(csrf_token), self._digest(token)),
            )
        return csrf_token

    def require_csrf(self, token: str | None, csrf_token: str | None) -> None:
        if not token or not csrf_token:
            raise BetaAccessDeniedError("csrf_required")
        with self._lock:
            row = self._connection.execute(
                "SELECT csrf_hash FROM beta_sessions WHERE session_hash = ?",
                (self._digest(token),),
            ).fetchone()
        if row is None or not hmac.compare_digest(
            row["csrf_hash"], self._digest(csrf_token)
        ):
            raise BetaAccessDeniedError("csrf_invalid")

    def logout(self, token: str | None) -> None:
        if token:
            self._delete_session(token)

    def get_user(self, user_id: str) -> BetaUserIdentity:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM beta_users WHERE user_id = ?",
                (str(user_id),),
            ).fetchone()
        if row is None:
            raise KeyError("beta_user_not_found")
        return self._identity(row)

    def list_users(self) -> dict[str, Any]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM beta_users ORDER BY created_at, email"
            ).fetchall()
        users = [self._identity(row).to_public_dict() for row in rows]
        now = _as_utc(self._now())
        active = 0
        expired = 0
        disabled = 0
        for user in users:
            if user["status"] == "disabled" or user["role"] == "disabled":
                disabled += 1
            elif user["role"] == "beta_user" and user["beta_expires_at"]:
                if _as_utc(user["beta_expires_at"]) <= now:
                    expired += 1
                else:
                    active += 1
            elif user["role"] == "admin":
                active += 1
        return {
            "users": users,
            "counts": {
                "total": len(users),
                "active": active,
                "expired": expired,
                "disabled": disabled,
            },
        }

    def set_enabled(self, user_id: str, *, enabled: bool) -> BetaUserIdentity:
        identity = self.get_user(user_id)
        if identity.role == "admin" and not enabled:
            admins = [
                user
                for user in self.list_users()["users"]
                if user["role"] == "admin" and user["status"] == "active"
            ]
            if len(admins) <= 1:
                raise BetaAccessDeniedError("last_admin_cannot_be_disabled")
        status = "active" if enabled else "disabled"
        role = "beta_user" if enabled and identity.role == "disabled" else identity.role
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE beta_users SET status = ?, role = ? WHERE user_id = ?",
                (status, role, identity.user_id),
            )
            if not enabled:
                self._connection.execute(
                    "DELETE FROM beta_sessions WHERE user_id = ?",
                    (identity.user_id,),
                )
        return self.get_user(identity.user_id)

    def extend_beta(
        self,
        user_id: str,
        *,
        days: int,
        now: datetime | None = None,
    ) -> BetaUserIdentity:
        if not isinstance(days, int) or not 1 <= days <= 3650:
            raise ValueError("days must be between 1 and 3650")
        identity = self.get_user(user_id)
        if identity.role != "beta_user":
            raise BetaAccessDeniedError("only_beta_users_can_be_extended")
        timestamp = _as_utc(now or self._now())
        current_expiry = (
            _as_utc(identity.beta_expires_at)
            if identity.beta_expires_at
            else timestamp
        )
        base = max(timestamp, current_expiry)
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE beta_users
                SET beta_start_at = COALESCE(beta_start_at, ?), beta_expires_at = ?
                WHERE user_id = ?
                """,
                (_iso(timestamp), _iso(base + timedelta(days=days)), identity.user_id),
            )
        return self.get_user(identity.user_id)

    def password_hash_for_audit(self, email: str) -> str:
        """Return only the one-way digest for security regression tests/audits."""
        row = self._find_user_row_by_email(self._normalize_email(email))
        if row is None:
            raise KeyError("beta_user_not_found")
        return str(row["password_hash"])

    def _delete_session(self, token: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM beta_sessions WHERE session_hash = ?",
                (self._digest(token),),
            )

    def _find_user_row_by_email(self, email: str) -> sqlite3.Row | None:
        with self._lock:
            return self._connection.execute(
                "SELECT * FROM beta_users WHERE email = ? COLLATE NOCASE",
                (email,),
            ).fetchone()

    @staticmethod
    def _normalize_email(email: str) -> str:
        if not isinstance(email, str):
            raise ValueError("invalid identity")
        normalized = email.strip().lower()
        if not normalized or len(normalized) > 320:
            raise ValueError("invalid identity")
        if "@" in normalized:
            if normalized.startswith("@") or normalized.endswith("@"):
                raise ValueError("invalid identity")
        elif re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,63}", normalized) is None:
            raise ValueError("invalid identity")
        return normalized

    @staticmethod
    def _identity(row: sqlite3.Row) -> BetaUserIdentity:
        return BetaUserIdentity(
            user_id=row["user_id"],
            email=row["email"],
            role=row["role"],
            status=row["status"],
            beta_start_at=row["beta_start_at"],
            beta_expires_at=row["beta_expires_at"],
            created_at=row["created_at"],
            last_login_at=row["last_login_at"],
        )

    @staticmethod
    def _digest(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _require_access(identity: BetaUserIdentity, now: datetime) -> None:
        if identity.status != "active" or identity.role == "disabled":
            raise BetaAccessDeniedError("beta_user_disabled")
        if identity.role == "admin":
            return
        if identity.role != "beta_user":
            raise BetaAccessDeniedError("beta_role_denied")
        if not identity.beta_start_at or not identity.beta_expires_at:
            raise BetaAccessDeniedError("beta_window_missing")
        if _as_utc(identity.beta_start_at) > now:
            raise BetaAccessDeniedError("beta_not_started")
        if _as_utc(identity.beta_expires_at) <= now:
            raise BetaAccessDeniedError("beta_expired")
