"""Read-only adapter for the isolated CURRENT ARMS PAPER runtime."""

from __future__ import annotations

from datetime import datetime, timezone
import http.client
import json
import math
import os
from pathlib import Path
import sqlite3
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request


PAPER_DASHBOARD_PATH = "/api/v2/backtesting/dashboard"
PAPER_HEALTH_PATH = "/health"
ANALYSIS_HEALTH_PATH = "/api/v2/market-analysis/health"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _timestamp(value: Any, *, now: datetime) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    if parsed > now:
        return None
    return parsed.isoformat()


def _loopback_base(value: str, *, name: str) -> str:
    parsed = urlparse(str(value).strip())
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or parsed.port is None
    ):
        raise ValueError(f"{name} must be an explicit loopback HTTP origin")
    return f"http://{parsed.netloc}"


class CurrentPaperReadOnlySourceV1:
    """Fetch canonical PAPER observations without exposing command authority."""

    is_canonical_current_paper_read_only = True

    def __init__(
        self,
        *,
        paper_base_url: str,
        analysis_base_url: str | None = None,
        database_path: str | Path | None = None,
        maximum_age_seconds: float = 120.0,
        request_timeout_seconds: float = 2.0,
        opener: Callable[..., Any] | None = None,
        now_provider: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.paper_base_url = _loopback_base(
            paper_base_url, name="paper_base_url"
        )
        self.analysis_base_url = (
            _loopback_base(analysis_base_url, name="analysis_base_url")
            if analysis_base_url
            else None
        )
        self.database_path = (
            Path(database_path).expanduser().resolve()
            if database_path
            else None
        )
        if not math.isfinite(maximum_age_seconds) or maximum_age_seconds <= 0:
            raise ValueError("maximum_age_seconds must be positive and finite")
        if not math.isfinite(request_timeout_seconds) or request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive and finite")
        self.maximum_age_seconds = float(maximum_age_seconds)
        self.request_timeout_seconds = float(request_timeout_seconds)
        self._opener = opener
        self._now = now_provider

    @classmethod
    def from_environment(cls) -> "CurrentPaperReadOnlySourceV1 | None":
        paper_url = os.getenv("ARMS_BETA_PAPER_BASE_URL", "").strip()
        if not paper_url:
            return None
        analysis_url = os.getenv("ARMS_BETA_ANALYSIS_BASE_URL", "").strip() or None
        database_path = os.getenv("ARMS_BETA_PAPER_DATABASE_PATH", "").strip() or None
        maximum_age = float(os.getenv("ARMS_BETA_MAXIMUM_DATA_AGE_SECONDS", "120"))
        timeout = float(os.getenv("ARMS_BETA_READ_TIMEOUT_SECONDS", "2"))
        return cls(
            paper_base_url=paper_url,
            analysis_base_url=analysis_url,
            database_path=database_path,
            maximum_age_seconds=maximum_age,
            request_timeout_seconds=timeout,
        )

    def get_snapshot(self) -> dict[str, Any]:
        now = self._now().astimezone(timezone.utc)
        paper_health = self._safe_fetch(self.paper_base_url + PAPER_HEALTH_PATH)
        response = self._safe_fetch(self.paper_base_url + PAPER_DASHBOARD_PATH)
        analysis_health = (
            self._safe_fetch(self.analysis_base_url + ANALYSIS_HEALTH_PATH)
            if self.analysis_base_url
            else None
        )
        paper = response.get("paper_research") if isinstance(response, dict) else None
        if not isinstance(paper, dict) or paper.get("mode") != "CURRENT_MARKET_PAPER":
            decisions, journal, history_available = self._read_history(now)
            snapshot = self._unavailable_snapshot(
                now, paper_health, analysis_health
            )
            if history_available:
                expired = dict(decisions[0]) if decisions else None
                if expired is not None:
                    expired["approved"] = False
                    expired["status"] = "EXPIRED"
                snapshot.update(
                    {
                        "execution_mode": "PAPER",
                        "runtime": {
                            "mode": "CURRENT_MARKET_PAPER",
                            "evidence_status": "HISTORICAL_QUERY_ONLY",
                        },
                        "current_signal": expired,
                        "signal_history": decisions,
                        "journal_history": journal,
                        "history_available": True,
                    }
                )
            return snapshot

        decisions, journal, history_available = self._read_history(now)
        market_data = paper.get("market_data")
        market_data = market_data if isinstance(market_data, dict) else {}
        heartbeat_at = _timestamp(market_data.get("last_received_time"), now=now)
        heartbeat_age = None
        if heartbeat_at:
            heartbeat_age = max(
                0.0,
                (now - datetime.fromisoformat(heartbeat_at)).total_seconds(),
            )
        provider_connected = market_data.get("connected") is True
        declared_freshness = str(paper.get("data_freshness") or "").upper()
        stale = (
            not provider_connected
            or heartbeat_age is None
            or heartbeat_age > self.maximum_age_seconds
            or declared_freshness not in {"FRESH", "CURRENT"}
        )
        runtime_status = "STALE" if stale else "CONNECTED"
        session = self._mapping(paper.get("session_state"))
        raw_session_status = str(session.get("state") or "UNAVAILABLE").upper()
        market_session_status = (
            "MAINTENANCE"
            if raw_session_status in {"MAINTENANCE", "DAILY_MAINTENANCE"}
            else raw_session_status
        )
        feed_freshness = "STALE_OR_UNAVAILABLE" if stale else "FRESH"
        authority_state = str(
            paper.get("paper_authority_state") or "UNAVAILABLE"
        ).upper()
        paper_api_status = str(
            (paper_health or {}).get("status") or "UNAVAILABLE"
        ).upper()
        paper_runtime_health = (
            "FAILED"
            if "FAIL" in authority_state
            or str(paper.get("dashboard_status") or "").upper()
            in {"FAILED", "RUNTIME_FAILURE"}
            else paper_api_status
        )
        paper_execution_authority = (
            "ENABLED"
            if paper.get("paper_execution_enabled") is True
            else "DISABLED"
        )
        latest_signal = decisions[0] if decisions else self._decision_signal(
            paper.get("latest_decision"),
            canonical_time=paper.get("canonical_time"),
            contract=paper.get("contract"),
            now=now,
        )
        positions = self._positions(paper.get("active_simulated_positions"), now)
        account = paper.get("account_overview")
        account = account if isinstance(account, dict) else {}
        live_allowed = paper.get("live_execution_allowed") is True
        return {
            "execution_mode": "PAPER" if not live_allowed else "UNAVAILABLE",
            "dashboard_status": str(paper.get("dashboard_status") or "UNAVAILABLE"),
            "runtime": {
                "mode": "CURRENT_MARKET_PAPER",
                "config_hash": str(paper.get("config_hash") or ""),
                "contract": str(paper.get("contract") or ""),
                "evidence_status": str(paper.get("evidence_status") or "UNAVAILABLE"),
            },
            "market_data": {
                "status": runtime_status,
                "provider_connected": provider_connected,
                "instrument": market_data.get("instrument"),
                "contract": market_data.get("contract") or paper.get("contract"),
                "heartbeat_at": heartbeat_at,
                "heartbeat_age_seconds": round(heartbeat_age, 3)
                if heartbeat_age is not None
                else None,
                "declared_freshness": declared_freshness or "UNAVAILABLE",
            },
            "market_session_status": market_session_status,
            "feed_freshness": feed_freshness,
            "paper_runtime_health": paper_runtime_health,
            "paper_execution_authority": paper_execution_authority,
            "live_execution_authority": "DISABLED",
            "session_state": session,
            "current_signal": latest_signal,
            "signal_history": decisions,
            "journal_history": journal,
            "history_available": history_available,
            "positions": positions,
            "current_position": positions[0] if positions else None,
            "runtime_observation": {
                "status": runtime_status,
                "paper_api_status": paper_api_status,
                "market_session_status": market_session_status,
                "feed_freshness": feed_freshness,
                "paper_runtime_health": paper_runtime_health,
                "paper_execution_authority": paper_execution_authority,
                "live_execution_authority": "DISABLED",
                "analysis_status": str(
                    (analysis_health or {}).get("phase") or "UNAVAILABLE"
                ),
                "ninjatrader_status": "CONNECTED"
                if provider_connected
                else "UNAVAILABLE",
                "heartbeat_at": heartbeat_at,
                "heartbeat_age_seconds": round(heartbeat_age, 3)
                if heartbeat_age is not None
                else None,
                "data_freshness": declared_freshness or "UNAVAILABLE",
                "paper_ready": paper.get("paper_ready") is True,
                "paper_authority_state": authority_state,
                "paper_execution_enabled": paper.get("paper_execution_enabled") is True,
                "live_execution_allowed": False,
                "analysis_only": (analysis_health or {}).get("analysis_only") is True,
                "order_submit_reachable": (
                    analysis_health or {}
                ).get("order_submit_reachable") is True,
                "contract": str(paper.get("contract") or "UNAVAILABLE"),
                "session_state": raw_session_status,
                "realized_paper_pnl": _finite(account.get("realized_pnl")),
                "current_position": positions[0] if positions else None,
                "read_only": True,
            },
        }

    def _safe_fetch(self, url: str) -> dict[str, Any] | None:
        try:
            if self._opener is not None:
                request = Request(
                    url,
                    headers={"Accept": "application/json"},
                    method="GET",
                )
                with self._opener(
                    request, timeout=self.request_timeout_seconds
                ) as response:
                    if getattr(response, "status", 200) != 200:
                        return None
                    raw = response.read()
            else:
                parsed = urlparse(url)
                connection = http.client.HTTPConnection(
                    parsed.hostname,
                    parsed.port,
                    timeout=self.request_timeout_seconds,
                )
                try:
                    connection.request(
                        "GET",
                        parsed.path,
                        headers={"Accept": "application/json"},
                    )
                    response = connection.getresponse()
                    if response.status != 200:
                        return None
                    raw = response.read()
                finally:
                    connection.close()
            payload = json.loads(raw.decode("utf-8"))
            return payload if isinstance(payload, dict) else None
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError):
            return None

    def _read_history(
        self, now: datetime
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
        if self.database_path is None or not self.database_path.is_file():
            return [], [], False
        try:
            uri = "file:" + self.database_path.as_posix() + "?mode=ro"
            connection = sqlite3.connect(uri, uri=True, timeout=1.0)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            decisions = []
            for row in connection.execute(
                """
                SELECT payload FROM decision_trace
                ORDER BY sequence DESC LIMIT 500
                """
            ):
                payload = json.loads(row["payload"])
                signal = self._decision_signal(payload, now=now)
                if signal is not None:
                    decisions.append(signal)
            journal = []
            for row in connection.execute(
                "SELECT payload FROM journal ORDER BY rowid DESC LIMIT 500"
            ):
                payload = json.loads(row["payload"])
                if isinstance(payload, dict):
                    journal.append(payload)
            connection.close()
            return decisions, journal, True
        except (OSError, sqlite3.Error, TypeError, ValueError, json.JSONDecodeError):
            return [], [], False

    @staticmethod
    def _mapping(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    def _decision_signal(
        self,
        value: Any,
        *,
        now: datetime,
        canonical_time: Any = None,
        contract: Any = None,
    ) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        observation = self._mapping(value.get("observation"))
        plan = self._mapping(value.get("plan"))
        action = str(value.get("action") or "HOLD").upper()
        approved = action in {"BUY", "SELL"} and bool(plan)
        timestamp = _timestamp(
            observation.get("canonical_timestamp") or canonical_time,
            now=now,
        )
        identity = (
            value.get("canonical_observation_id")
            or observation.get("event_id")
            or value.get("event_id")
        )
        return {
            "signal_id": str(identity or ""),
            "symbol": str(observation.get("instrument") or ""),
            "contract": str(observation.get("contract") or contract or ""),
            "action": action,
            "approved": approved,
            "status": "ACTIVE" if approved else "CANCELLED",
            "probability": _finite(value.get("confidence")),
            "confluence": _finite(
                value.get("confluence_score")
                if value.get("confluence_score") is not None
                else self._mapping(value.get("metadata")).get("confluence_score")
            ),
            "entry_price": _finite(plan.get("entry_price") or plan.get("entry")),
            "stop_loss": _finite(plan.get("stop_loss") or plan.get("stop")),
            "take_profit": _finite(plan.get("take_profit") or plan.get("target")),
            "reward_risk": _finite(
                plan.get("reward_risk") or plan.get("risk_reward_ratio")
            ),
            "generated_at": timestamp,
            "decision_reason": str(
                value.get("decision_reason") or value.get("reason") or ""
            ),
            "market_data": {"status": "AVAILABLE"},
        }

    @staticmethod
    def _positions(value: Any, now: datetime) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        positions = []
        for raw in value:
            if not isinstance(raw, dict):
                continue
            positions.append(
                {
                    "position_id": str(raw.get("position_id") or raw.get("id") or ""),
                    "instrument": str(raw.get("symbol") or raw.get("instrument") or ""),
                    "direction": str(raw.get("direction") or "UNAVAILABLE").upper(),
                    "quantity": _finite(raw.get("quantity") or raw.get("contracts")),
                    "entry_price": _finite(raw.get("entry_price") or raw.get("entry")),
                    "stop_loss": _finite(raw.get("stop_loss") or raw.get("stop")),
                    "take_profit": _finite(raw.get("take_profit") or raw.get("target")),
                    "unrealized_pnl": _finite(raw.get("unrealized_pnl")),
                    "opened_at": _timestamp(
                        raw.get("opened_at") or raw.get("created_at"), now=now
                    ),
                    "status": str(raw.get("status") or "OPEN").upper(),
                    "paper_only": True,
                }
            )
        return positions

    @staticmethod
    def _unavailable_snapshot(
        now: datetime,
        paper_health: dict[str, Any] | None,
        analysis_health: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "dashboard_status": "UNAVAILABLE",
            "market_data": {"status": "UNAVAILABLE"},
            "market_session_status": "UNAVAILABLE",
            "feed_freshness": "UNAVAILABLE",
            "paper_runtime_health": str(
                (paper_health or {}).get("status") or "UNAVAILABLE"
            ).upper(),
            "paper_execution_authority": "DISABLED",
            "live_execution_authority": "DISABLED",
            "history_available": False,
            "signal_history": [],
            "journal_history": [],
            "positions": [],
            "current_position": None,
            "runtime_observation": {
                "status": "UNAVAILABLE",
                "paper_api_status": str(
                    (paper_health or {}).get("status") or "UNAVAILABLE"
                ),
                "analysis_status": str(
                    (analysis_health or {}).get("phase") or "UNAVAILABLE"
                ),
                "ninjatrader_status": "UNAVAILABLE",
                "heartbeat_at": None,
                "heartbeat_age_seconds": None,
                "data_freshness": "UNAVAILABLE",
                "market_session_status": "UNAVAILABLE",
                "feed_freshness": "UNAVAILABLE",
                "paper_runtime_health": str(
                    (paper_health or {}).get("status") or "UNAVAILABLE"
                ).upper(),
                "paper_execution_authority": "DISABLED",
                "live_execution_authority": "DISABLED",
                "paper_ready": False,
                "paper_authority_state": "UNAVAILABLE",
                "paper_execution_enabled": False,
                "live_execution_allowed": False,
                "analysis_only": True,
                "order_submit_reachable": False,
                "contract": "UNAVAILABLE",
                "session_state": "UNAVAILABLE",
                "realized_paper_pnl": None,
                "current_position": None,
                "read_only": True,
                "observed_at": now.isoformat(),
            },
        }
