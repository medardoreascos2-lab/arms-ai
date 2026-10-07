"""Sanitized, read-only Beta Dashboard V1 projections."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from typing import Any

from backend.api.dashboard_browser_transport_v11 import dashboard_snapshot


CONTRACT_VERSION = "1.0"
SIGNAL_STATUSES = frozenset(
    {"WAITING", "ACTIVE", "TARGET_HIT", "STOPPED", "CANCELLED", "EXPIRED"}
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    if parsed > _now():
        return None
    return parsed.isoformat()


def _direction(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in {"BUY", "LONG", "BULLISH"}:
        return "BUY"
    if normalized in {"SELL", "SHORT", "BEARISH"}:
        return "SELL"
    return "NO_TRADE"


def _runtime_id(runtime: Any) -> str | None:
    if not isinstance(runtime, dict) or not runtime:
        return None
    canonical = json.dumps(runtime, sort_keys=True, default=str, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()[:20]


def _signal_id(signal: dict[str, Any], source_runtime_id: str | None) -> str:
    existing = signal.get("signal_id") or signal.get("id")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()
    stable = {
        "source_runtime_id": source_runtime_id,
        "instrument": signal.get("symbol") or signal.get("instrument"),
        "created_at": signal.get("generated_at") or signal.get("created_at"),
        "action": signal.get("action") or signal.get("direction"),
        "entry_price": signal.get("entry_price") or signal.get("entry"),
    }
    encoded = json.dumps(stable, sort_keys=True, default=str, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def _decision_summary(signal: dict[str, Any] | None, approved: bool) -> str:
    if signal is None:
        return "Waiting for an eligible PAPER signal."
    reason = str(signal.get("decision_reason") or "").strip()
    if not approved:
        return (
            f"No PAPER signal: {reason}"
            if reason
            else "No PAPER signal: ARMS requirements were not satisfied."
        )
    return "PAPER signal passed the ARMS decision and risk checks."


class BetaDashboardProjectionV1:
    """Projects existing PAPER stores without exposing execution authority."""

    def __init__(self, *, symbol: str | None = None, timeframe: str | None = None):
        self.symbol = (symbol or os.getenv("ARMS_BETA_SYMBOL", "MNQ")).strip().upper()
        self.timeframe = (
            timeframe or os.getenv("ARMS_BETA_TIMEFRAME", "5m")
        ).strip().lower()
        if not self.symbol or not self.timeframe:
            raise ValueError("beta symbol and timeframe are required")

    def build(self, state: Any, live_data_service: Any) -> dict[str, Any]:
        observed_at = _now().isoformat()
        if getattr(
            live_data_service, "is_canonical_current_paper_read_only", False
        ):
            snapshot = live_data_service.get_snapshot() or {}
        else:
            snapshot = dashboard_snapshot(state, live_data_service) or {}
        if not isinstance(snapshot, dict):
            snapshot = {}
        paper_verified = snapshot.get("execution_mode") == "PAPER"
        runtime_id = _runtime_id(snapshot.get("runtime")) if paper_verified else None
        signal = self._latest_signal(state, snapshot) if paper_verified else None
        analysis = self._latest_analysis(state) if paper_verified else None
        current = self._current_signal(signal, runtime_id, observed_at)
        history = self._history(state, snapshot, runtime_id) if paper_verified else []
        market_data = snapshot.get("market_data")
        market_data = market_data if isinstance(market_data, dict) else {}
        instrument = str(
            (signal or {}).get("symbol")
            or market_data.get("instrument")
            or self.symbol
        )
        contract = str(
            (signal or {}).get("contract")
            or market_data.get("contract")
            or snapshot.get("contract")
            or instrument
        )
        history_available = snapshot.get("history_available")
        return {
            "contract_version": CONTRACT_VERSION,
            "observed_at": observed_at,
            "paper_only": True,
            "product_state": "BETA",
            "disclaimer": "PAPER / SIMULATED RESULTS â€” NOT LIVE BROKER PERFORMANCE",
            "live": {
                "arms_status": str(snapshot.get("dashboard_status", "UNAVAILABLE")),
                "market_status": self._market_status(snapshot, signal, analysis),
                "instrument": instrument,
                "contract": contract,
                "current_signal": current["direction"],
                "signal": current,
                "position": snapshot.get("current_position")
                if isinstance(snapshot.get("current_position"), dict)
                else None,
            },
            "history": {
                "status": "AVAILABLE"
                if paper_verified and history_available is not False
                else "UNAVAILABLE",
                "records": history,
            },
            "performance": self._performance(history, observed_at),
            "runtime": self._runtime_observation(snapshot),
        }
    def _latest_signal(
        self, state: Any, snapshot: dict[str, Any]
    ) -> dict[str, Any] | None:
        canonical = snapshot.get("current_signal")
        if isinstance(canonical, dict):
            return canonical
        store = getattr(state, "live_signal_store", None)
        reader = getattr(store, "get_latest", None)
        if not callable(reader):
            return None
        result = reader(symbol=self.symbol, timeframe=self.timeframe)
        return result if isinstance(result, dict) else None

    def _latest_analysis(self, state: Any) -> dict[str, Any] | None:
        store = getattr(state, "live_analysis_store", None)
        reader = getattr(store, "get_latest", None)
        if not callable(reader):
            return None
        result = reader(symbol=self.symbol, timeframe=self.timeframe)
        return result if isinstance(result, dict) else None

    @staticmethod
    def _market_status(
        snapshot: dict[str, Any],
        signal: dict[str, Any] | None,
        analysis: dict[str, Any] | None,
    ) -> str:
        canonical = snapshot.get("market_data")
        if isinstance(canonical, dict) and canonical.get("status"):
            return str(canonical["status"]).upper()
        for source in (signal, analysis):
            market_data = source.get("market_data") if isinstance(source, dict) else None
            if isinstance(market_data, dict) and market_data.get("status"):
                return str(market_data["status"]).upper()
        return "UNAVAILABLE"

    @staticmethod
    def _runtime_observation(snapshot: dict[str, Any]) -> dict[str, Any]:
        raw = snapshot.get("runtime_observation")
        if not isinstance(raw, dict):
            raw = {}
        return {
            "status": str(raw.get("status") or "UNAVAILABLE"),
            "paper_api_status": str(raw.get("paper_api_status") or "UNAVAILABLE"),
            "analysis_status": str(raw.get("analysis_status") or "UNAVAILABLE"),
            "ninjatrader_status": str(raw.get("ninjatrader_status") or "UNAVAILABLE"),
            "heartbeat_at": _iso(raw.get("heartbeat_at")),
            "heartbeat_age_seconds": _number(raw.get("heartbeat_age_seconds")),
            "data_freshness": str(raw.get("data_freshness") or "UNAVAILABLE"),
            "market_session_status": str(
                raw.get("market_session_status") or "UNAVAILABLE"
            ),
            "feed_freshness": str(raw.get("feed_freshness") or "UNAVAILABLE"),
            "paper_runtime_health": str(
                raw.get("paper_runtime_health") or "UNAVAILABLE"
            ),
            "paper_execution_authority": str(
                raw.get("paper_execution_authority") or "DISABLED"
            ),
            "live_execution_authority": "DISABLED",
            "paper_ready": raw.get("paper_ready") is True,
            "paper_authority_state": str(
                raw.get("paper_authority_state") or "UNAVAILABLE"
            ),
            "paper_execution_enabled": raw.get("paper_execution_enabled") is True,
            "live_execution_allowed": False,
            "analysis_only": raw.get("analysis_only") is True,
            "order_submit_reachable": raw.get("order_submit_reachable") is True,
            "contract": str(raw.get("contract") or "UNAVAILABLE"),
            "session_state": str(raw.get("session_state") or "UNAVAILABLE"),
            "realized_paper_pnl": _number(raw.get("realized_paper_pnl")),
            "current_position": raw.get("current_position")
            if isinstance(raw.get("current_position"), dict)
            else None,
            "read_only": True,
        }

    def _current_signal(
        self,
        signal: dict[str, Any] | None,
        runtime_id: str | None,
        observed_at: str,
    ) -> dict[str, Any]:
        approved = bool(signal and signal.get("approved") is True)
        direction = _direction(
            (signal or {}).get("action") or (signal or {}).get("direction")
        )
        if not approved:
            direction = "NO_TRADE" if signal else "WAITING"
        raw_status = str((signal or {}).get("status") or "").strip().upper()
        status = raw_status if raw_status in SIGNAL_STATUSES else (
            "ACTIVE" if approved else "CANCELLED" if signal else "WAITING"
        )
        created_at = _iso(
            (signal or {}).get("generated_at")
            or (signal or {}).get("created_at")
            or (signal or {}).get("timestamp")
        )
        source = signal or {"symbol": self.symbol, "action": "WAITING"}
        return {
            "signal_id": _signal_id(source, runtime_id),
            "created_at": created_at,
            "updated_at": _iso((signal or {}).get("updated_at")) or created_at,
            "instrument": str((signal or {}).get("symbol") or self.symbol),
            "contract": str((signal or {}).get("contract") or self.symbol),
            "direction": direction,
            "status": status,
            "entry_price": _number((signal or {}).get("entry_price")) if approved else None,
            "stop_loss": _number((signal or {}).get("stop_loss")) if approved else None,
            "take_profit": _number((signal or {}).get("take_profit")) if approved else None,
            "reward_risk": _number(
                (signal or {}).get("reward_risk")
                or (signal or {}).get("risk_reward_ratio")
            ) if approved else None,
            "confidence": _number((signal or {}).get("probability")),
            "confluence": _number((signal or {}).get("confluence")),
            "paper_only": True,
            "source_runtime_id": runtime_id,
            "decision_summary": _decision_summary(signal, approved),
            "result": (signal or {}).get("result"),
            "exit_price": _number((signal or {}).get("exit_price")),
            "exit_at": _iso((signal or {}).get("exit_at")),
            "paper_pnl": _number((signal or {}).get("paper_pnl")),
        }

    def _history(
        self,
        state: Any,
        snapshot: dict[str, Any],
        runtime_id: str | None,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        journal = snapshot.get("journal_history")
        if isinstance(journal, list):
            for item in journal:
                if isinstance(item, dict):
                    records.append(self._journal_record(item, runtime_id))
        canonical_signals = snapshot.get("signal_history")
        if isinstance(canonical_signals, list):
            for signal in canonical_signals:
                if isinstance(signal, dict):
                    records.append(self._signal_history_record(signal, runtime_id))
        else:
            store = getattr(state, "signal_history_store", None)
            reader = getattr(store, "get_history", None)
            if callable(reader):
                signals = reader(symbol=self.symbol, timeframe=self.timeframe, limit=500)
                if isinstance(signals, list):
                    for signal in signals:
                        if isinstance(signal, dict):
                            records.append(
                                self._signal_history_record(signal, runtime_id)
                            )
        deduplicated: dict[str, dict[str, Any]] = {}
        for record in records:
            key = str(record["record_id"])
            existing = deduplicated.get(key)
            if existing is None or bool(record.get("exit_time")):
                deduplicated[key] = record
        return sorted(
            deduplicated.values(),
            key=lambda record: str(record.get("entry_time") or ""),
            reverse=True,
        )

    def _journal_record(
        self, trade: dict[str, Any], runtime_id: str | None
    ) -> dict[str, Any]:
        direction = _direction(trade.get("direction"))
        entry = _number(trade.get("entry") or trade.get("entry_price"))
        exit_price = _number(trade.get("exit_price"))
        status = str(trade.get("status") or "UNAVAILABLE").upper()
        result = str(trade.get("result") or trade.get("exit_reason") or status).upper()
        points = None
        if entry is not None and exit_price not in {None, 0.0}:
            points = exit_price - entry if direction == "BUY" else entry - exit_price
        identity = str(
            trade.get("trade_id")
            or trade.get("position_id")
            or _signal_id(trade, runtime_id)
        )
        return {
            "record_id": identity,
            "record_type": "PAPER_TRADE",
            "instrument": str(trade.get("symbol") or self.symbol),
            "direction": direction,
            "entry": entry,
            "stop": _number(trade.get("stop_loss") or trade.get("stop")),
            "target": _number(trade.get("take_profit") or trade.get("target")),
            "entry_time": _iso(trade.get("created_at") or trade.get("entry_time")),
            "exit_time": _iso(trade.get("closed_at") or trade.get("exit_time")),
            "exit_price": exit_price if exit_price not in {0.0} else None,
            "result": result,
            "points_or_ticks": round(points, 8) if points is not None else None,
            "points_or_ticks_unit": "POINTS" if points is not None else None,
            "paper_pnl": _number(
                trade.get("pnl")
                if trade.get("pnl") is not None
                else trade.get("realized_pnl")
            ),
            "status": status,
            "paper_only": True,
            "source_runtime_id": runtime_id,
        }

    def _signal_history_record(
        self, signal: dict[str, Any], runtime_id: str | None
    ) -> dict[str, Any]:
        approved = signal.get("approved") is True
        direction = _direction(signal.get("action") or signal.get("direction"))
        if not approved:
            direction = "NO_TRADE"
        status = str(signal.get("status") or (
            "WAITING" if approved else "CANCELLED"
        )).upper()
        identity = _signal_id(signal, runtime_id)
        return {
            "record_id": identity,
            "record_type": "PAPER_SIGNAL",
            "instrument": str(signal.get("symbol") or self.symbol),
            "direction": direction,
            "entry": _number(signal.get("entry_price")) if approved else None,
            "stop": _number(signal.get("stop_loss")) if approved else None,
            "target": _number(signal.get("take_profit")) if approved else None,
            "entry_time": _iso(
                signal.get("generated_at")
                or signal.get("created_at")
                or signal.get("timestamp")
            ),
            "exit_time": _iso(signal.get("exit_at")),
            "exit_price": _number(signal.get("exit_price")),
            "result": signal.get("result"),
            "points_or_ticks": None,
            "points_or_ticks_unit": None,
            "paper_pnl": _number(signal.get("paper_pnl")),
            "status": status,
            "paper_only": True,
            "source_runtime_id": runtime_id,
        }

    @staticmethod
    def _performance(
        history: list[dict[str, Any]], observed_at: str
    ) -> dict[str, Any]:
        trades = [
            row for row in history
            if row.get("record_type") == "PAPER_TRADE"
            and str(row.get("status", "")).upper() not in {"OPEN", "ACTIVE"}
        ]
        pnl_values = [row.get("paper_pnl") for row in trades]
        reliable = bool(trades) and all(isinstance(value, (int, float)) for value in pnl_values)
        unavailable = {
            "today_pnl": "insufficient data",
            "cumulative_pnl": "insufficient data",
            "trades": "available",
            "wins": "insufficient data",
            "losses": "insufficient data",
            "win_rate": "insufficient data",
            "average_win": "insufficient data",
            "average_loss": "insufficient data",
            "profit_factor": "insufficient data",
            "maximum_drawdown": "insufficient data",
        }
        result: dict[str, Any] = {
            "paper_only": True,
            "as_of": observed_at,
            "today_pnl": None,
            "cumulative_pnl": None,
            "trades": len(trades),
            "wins": None,
            "losses": None,
            "win_rate": None,
            "average_win": None,
            "average_loss": None,
            "profit_factor": None,
            "maximum_drawdown": None,
            "availability": unavailable,
        }
        if not reliable:
            return result
        values = [float(value) for value in pnl_values]
        wins = [value for value in values if value > 0]
        losses = [value for value in values if value < 0]
        cumulative = sum(values)
        peak = 0.0
        running = 0.0
        maximum_drawdown = 0.0
        for value in reversed(values):
            running += value
            peak = max(peak, running)
            maximum_drawdown = max(maximum_drawdown, peak - running)
        observed_date = datetime.fromisoformat(observed_at).date()
        today_values: list[float] = []
        today_reliable = True
        for row, value in zip(trades, values):
            exit_at = _iso(row.get("exit_time"))
            if exit_at is None:
                today_reliable = False
                break
            if datetime.fromisoformat(exit_at).date() == observed_date:
                today_values.append(value)
        result.update(
            {
                "today_pnl": round(sum(today_values), 2) if today_reliable else None,
                "cumulative_pnl": round(cumulative, 2),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": round(len(wins) / len(trades) * 100, 2),
                "average_win": round(sum(wins) / len(wins), 2) if wins else None,
                "average_loss": round(sum(losses) / len(losses), 2) if losses else None,
                "profit_factor": (
                    round(sum(wins) / abs(sum(losses)), 4) if wins and losses else None
                ),
                "maximum_drawdown": round(maximum_drawdown, 2),
            }
        )
        for field in (
            "cumulative_pnl", "wins", "losses", "win_rate", "maximum_drawdown"
        ):
            unavailable[field] = "available"
        if today_reliable:
            unavailable["today_pnl"] = "available"
        if wins:
            unavailable["average_win"] = "available"
        if losses:
            unavailable["average_loss"] = "available"
        if wins and losses:
            unavailable["profit_factor"] = "available"
        return result
