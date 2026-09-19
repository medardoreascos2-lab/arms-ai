"""Opt-in, serialized certified replay PAPER runtime with restart containment.

The durable store is evidence, not an alternative account or execution authority.
An existing namespace NEVER constructs a fresh financial runtime or resumes it.
"""
from copy import deepcopy
from contextlib import closing
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from threading import RLock

from backend.backtesting.closed_bar_aggregator_v1 import ClosedBarAggregatorV1
from backend.backtesting.paper_research_v1 import PaperResearchSessionV1
from backend.strategies.trading_strategy_v2 import TradingActionV2, TradingDecisionV2


class OperatingModeV1(str, Enum):
    PRODUCTION_POLICY = "PRODUCTION_POLICY"
    PAPER_RESEARCH = "PAPER_RESEARCH"
    HISTORICAL_RESEARCH = "HISTORICAL_RESEARCH"


def _plain(value):
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    return value


def _encode(value):
    return json.dumps(_plain(value), sort_keys=True, allow_nan=False, separators=(",", ":"))


class PaperRuntimeV1:
    """One explicitly new isolated account per durable namespace.

    Input and delivery clock are historical replay time, never wall time. Entry
    controls do not disable canonical exits on subsequent valid observations.
    All public reads return detached, already-published state without marking.
    """
    def __init__(self, *, mode, config, settings, policy, observations, contract,
                 state_path, initialization_policy):
        if OperatingModeV1(mode) is not OperatingModeV1.PAPER_RESEARCH:
            raise ValueError("incremental execution requires explicit PAPER_RESEARCH")
        if initialization_policy != "NEW_ISOLATED_PAPER_ACCOUNT":
            raise ValueError("explicit new isolated account policy required")
        self._lock = RLock()
        self._db = None
        self._paper = None
        self._stopped = False
        self._enabled = False
        self._emergency = False
        self._fault = None
        self._fault_detail = None
        self._cursor = 0
        self._strategy_evidence = {}
        self._last_decision = None
        self._last_submission = None
        self._last_plan = None
        self._risk = []
        self._anomalies = 0
        self._risk_vetoes = 0
        self._path = Path(state_path)
        self._max_age = settings.maximum_quote_age_seconds
        self._snapshot = {"mode": mode, "dashboard_status": "RECOVERY_REQUIRED",
                          "paper_ready": False, "readiness_reasons": ["RECOVERY_REQUIRED"],
                          "live_execution_allowed": False, "operational_state_restored": False,
                          "account_overview": None, "config_hash": None}
        # Exclusive creation prevents two writers or accidental account reset.
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._path.open("xb"):
                pass
        except FileExistsError:
            self._recover_evidence()
            return
        try:
            self._rows = tuple(observations)
            self._paper = PaperResearchSessionV1(config=config, settings=settings, policy=policy,
                                                observations=self._rows, contract=contract)
            r = self._paper.runtime
            self._authorities = self._authority_bindings()
            self._policy_identity = self._policy_settings()
            self._htf = ClosedBarAggregatorV1(history_limit=r.session.analysis_window)
            self._identity = sha256(_encode({"account_config": r.config_hash,
                "paper": asdict(config), "mode": mode, "clock": "CERTIFIED_REPLAY",
                "effective_policy": self._policy_identity,
                "maximum_quote_age_seconds": self._max_age,
                "input": [(x.source_sha256, x.source_row, x.raw_row) for x in self._rows]}).encode()).hexdigest()
            self._db = sqlite3.connect(self._path, check_same_thread=False)
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.executescript("""
                CREATE TABLE checkpoint (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT, digest TEXT);
                CREATE TABLE events (id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL UNIQUE, phase TEXT NOT NULL);
                CREATE TABLE journal (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """)
            self._observe_strategy()
            self._publish()
            self._save()
        except BaseException:
            self._fault = "RECOVERY_REQUIRED"
            if self._db is not None:
                self._db.close()
                self._db = None
            # Preserve the namespace even if initialization failed.
            raise

    def _recover_evidence(self):
        try:
            with closing(sqlite3.connect(self._path.resolve().as_uri()+"?mode=ro", uri=True)) as db:
                payload, digest = db.execute("SELECT payload,digest FROM checkpoint WHERE id=1").fetchone()
                if sha256(payload.encode()).hexdigest() != digest:
                    raise ValueError("checkpoint checksum mismatch")
                saved = json.loads(payload)
                pending = db.execute("SELECT count(*) FROM events WHERE phase='INFLIGHT'").fetchone()[0]
                self._snapshot.update(saved)
                self._snapshot["pending_events"] = pending
                self._snapshot["evidence_status"] = "LAST_COMMITTED_NOT_OPERATIONALLY_RESTORED"
        except (sqlite3.Error, ValueError, TypeError):
            self._snapshot["evidence_status"] = "UNREADABLE_RECONCILIATION_REQUIRED"
        self._snapshot.update(dashboard_status="RECOVERY_REQUIRED", paper_ready=False,
                              readiness_reasons=["RECOVERY_REQUIRED"], operational_state_restored=False,
                              paper_execution_enabled=False)

    def _observe_strategy(self):
        strategy = self._paper.runtime.session.strategy_runner_v2
        components = (("structure", "market_structure_engine", "analyze"),
                      ("trend", "trend_context_engine", "analyze"),
                      ("liquidity", "liquidity_engine", "analyze"),
                      ("fvg", "smart_money_engine", "detect_fvg"),
                      ("regime", "market_regime_engine", "evaluate"),
                      ("confluence", "confluence_engine", "evaluate"),
                      ("quality", "trade_quality_engine", "evaluate"))
        for name, attribute, method in components:
            owner = getattr(strategy, attribute)
            original = getattr(owner, method)
            def observe(*args, _name=name, _original=original, _owner=owner, **kwargs):
                result = _original(*args, **kwargs)
                evidence = result
                if _name == "liquidity" and result is None:
                    evidence = {k: getattr(_owner, k, None) for k in
                                ("sweep_detected", "sweep_direction", "liquidity_level")}
                self._strategy_evidence[_name] = _plain(evidence)
                return result
            setattr(owner, method, observe)

    def _authority_reasons(self):
        r = self._paper.runtime
        life = r.lifecycle
        if (any(a is not b for a, b in zip(self._authorities, self._authority_bindings())) or
            r.session.signal_submission_target_v2 is not life or
            life.portfolio_manager_v2 is not r.portfolio or life.trade_journal_v2 is not r.journal or
            r.portfolio.account_state_manager_v2 is not r.account or
            life.execution_manager.execution_mode != "PAPER" or
            r.session.trade_executor_v2 is not None or self._policy_settings() != self._policy_identity):
            return ["AUTHORITY_UNAVAILABLE"]
        return []

    def _policy_settings(self):
        r = self._paper.runtime
        risk = r.lifecycle.risk_manager_v2
        signal = r.session.signal_generator_v2
        return {"risk_percent": r.risk_percent,
                "maximum_daily_loss": risk.maximum_daily_loss,
                "maximum_total_drawdown": risk.maximum_total_drawdown,
                "maximum_contracts": risk.maximum_contracts,
                "maximum_open_positions": risk.maximum_open_positions,
                "minimum_signal_probability": signal.minimum_probability,
                "minimum_signal_confluence": signal.minimum_confluence_score,
                "minimum_candles": r.engine.minimum_candles,
                "analysis_window": r.session.analysis_window,
                "costs": asdict(r.costs),
                "paper_slippage_points": r.lifecycle.paper_execution_engine.slippage_points}

    def _authority_bindings(self):
        r = self._paper.runtime
        life = r.lifecycle
        return (r.account, r.portfolio, r.journal, r.session.strategy_runner_v2,
                r.session.signal_generator_v2, r.session.backtest_trade_plan_adapter_v2,
                r.session.risk_pipeline, life.risk_manager_v2, life.execution_risk_gate_v1,
                life.execution_manager, life.paper_execution_engine, life.position_manager,
                life.broker_connector_v2)

    def _reasons(self):
        reasons = self._authority_reasons()
        if self._stopped:
            reasons.append("STOPPED")
        if self._fault:
            reasons.append(self._fault)
        if not self._enabled:
            reasons.append("PAPER_DISABLED")
        if self._emergency:
            reasons.append("EMERGENCY_BLOCK")
        if self._paper.runtime.index == 0:
            reasons.append("AWAITING_MARKET_DATA")
        if self._cursor == len(self._rows):
            reasons.append("END_OF_DATA")
        account = self._paper.runtime.account.get_state()
        if account["trading_blocked"]:
            reasons.extend(account["blocking_reasons"] or ["RISK_BLOCKED"])
        return reasons

    def _publish(self):
        r = self._paper.runtime
        reasons = self._reasons()
        self._snapshot = {**self._paper._capture("PAPER_READY" if not reasons else "BLOCKED"),
            "config_hash": self._identity, "account_config_hash": r.config_hash,
            "effective_policy": deepcopy(self._policy_identity),
            "paper_ready": not reasons, "readiness_reasons": reasons,
            "operational_state_restored": False, "evidence_status": "CURRENT_PROCESS",
            "clock": "CERTIFIED_REPLAY", "paper_execution_enabled": self._enabled,
            "emergency_block": self._emergency, "source_observations_processed": self._cursor,
            "fault_detail": self._fault_detail,
            "anomalies_excluded": self._anomalies,
            "timeframe_readiness": {"1m": len(r.session.candle_history),
                **{tf: len(self._htf.history(tf)) for tf in ("15m", "1h")}},
            "htf_emitted": dict(self._htf.emitted_counts),
            "strategy_evidence": deepcopy(self._strategy_evidence),
            "latest_decision": _plain(self._last_decision), "risk_evaluation": _plain(self._risk),
            "plan": _plain(self._last_plan), "submission": _plain(self._last_submission),
            "execution_state": "OPEN" if r.lifecycle.get_active_positions() else "FLAT",
            "canonical_time": r.current.available_at.isoformat() if r.index else None,
            "journal_total": len(r.journal.trades)}
        self._snapshot["risk_vetoes"] = self._risk_vetoes
        self._snapshot = _plain(self._snapshot)

    def _save(self):
        payload = _encode(self._snapshot)
        self._db.execute("INSERT OR REPLACE INTO checkpoint VALUES(1,?,?)",
                         (payload, sha256(payload.encode()).hexdigest()))
        self._db.commit()

    def get_snapshot(self):
        with self._lock:
            snapshot = deepcopy(self._snapshot)
            if self._paper is not None and self._authority_reasons():
                snapshot.update(paper_ready=False, dashboard_status="BLOCKED")
                snapshot["readiness_reasons"] = list(dict.fromkeys(
                    snapshot["readiness_reasons"] + ["AUTHORITY_UNAVAILABLE"]))
            return snapshot

    def control(self, command):
        with self._lock:
            if self._paper is None or self._stopped or self._fault:
                raise RuntimeError("RECOVERY_REQUIRED or stopped runtime")
            if command == "enable":
                self._enabled = True
            elif command == "disable":
                self._enabled = False
            elif command == "emergency_block":
                self._emergency = True  # Latched for this namespace; no reset endpoint.
            else:
                raise ValueError("unknown PAPER control")
            try:
                self._publish()
                self._save()
            except Exception:
                self._fault = "RECOVERY_REQUIRED"
                self._enabled = False
                self._publish()
                raise
            return self.get_snapshot()

    def step(self):
        """Explicit replay delivery command, not a read or live-feed adapter."""
        with self._lock:
            if self._paper is None or self._cursor >= len(self._rows):
                raise RuntimeError("RECOVERY_REQUIRED or END_OF_DATA")
            row = self._rows[self._cursor]
            return self.ingest(row, received_at=row.available_at)

    def ingest(self, observation, *, received_at):
        with self._lock:
            if self._paper is None or self._stopped or self._fault:
                raise RuntimeError("RECOVERY_REQUIRED or stopped runtime")
            fingerprint = sha256(repr(observation).encode()).hexdigest()
            try:
                # Duplicate lookup precedes chronology; only an identical completed event is a no-op.
                prior = self._db.execute("SELECT phase FROM events WHERE fingerprint=?", (fingerprint,)).fetchone()
                if prior and prior[0] == "COMPLETED":
                    return self.get_snapshot()
                if self._authority_reasons():
                    raise ValueError("AUTHORITY_UNAVAILABLE")
                if self._cursor >= len(self._rows) or observation != self._rows[self._cursor]:
                    raise ValueError("OUT_OF_ORDER_OR_CONFLICTING_INPUT")
                if received_at.tzinfo is None:
                    raise ValueError("INVALID_REPLAY_CLOCK")
                age = (received_at.astimezone(timezone.utc)-observation.available_at).total_seconds()
                if not 0 <= age <= self._max_age:
                    raise ValueError("STALE_OR_FUTURE_INPUT")
                self._db.execute("INSERT INTO events VALUES(?,?,'INFLIGHT')", (self._cursor, fingerprint))
                self._db.commit()  # Durable uncertainty before ANY account/strategy mutation.
                r = self._paper.runtime
                before = len(r.completed)
                if (observation.strategy_context_eligible and observation.execution_price_eligible
                        and observation.session_accounting_eligible):
                    self._process(observation)
                else:
                    self._anomalies += 1
                self._cursor += 1
                self._publish()
                for trade in r.completed[before:]:
                    self._db.execute("INSERT INTO journal VALUES(?,?)", (trade["position_id"], _encode(trade)))
                self._db.execute("UPDATE events SET phase='COMPLETED' WHERE id=?", (self._cursor-1,))
                self._save()  # Snapshot, completed event and journal share one transaction.
            except Exception as exc:
                self._fault = "RECOVERY_REQUIRED"
                self._fault_detail = type(exc).__name__ + ": " + str(exc)
                self._enabled = False
                try:
                    self._db.rollback()
                except sqlite3.Error:
                    pass  # Loss of storage cannot bypass containment.
                self._publish()
                raise
            return self.get_snapshot()

    def _process(self, observation):
        r = self._paper.runtime
        s = r.session
        candle = observation.candle()
        normalized = s._normalize_candle(candle)
        self._strategy_evidence = dict.fromkeys(("trend", "structure", "liquidity", "fvg", "regime", "confluence", "quality"))
        self._last_decision = self._last_submission = self._last_plan = None
        self._risk = []
        s._update_active_position_if_configured(candle=normalized)
        s.candle_history.append(normalized)
        del s.candle_history[:-s.analysis_window]
        self._htf.update_completed(candle)
        if r.engine.minimum_candles <= r.index < len(r.rows):
            context = {"candle": normalized, "history": list(s.candle_history),
                "history_15m": [s._normalize_candle(x) for x in self._htf.history("15m")],
                "history_1h": [s._normalize_candle(x) for x in self._htf.history("1h")],
                "signal_index": r.index, "decision_time": self._htf.available_at,
                "publish_result": None, "active_position_id": s.active_position_id,
                "has_active_position": s.active_position_id is not None}
            decision = s.strategy_runner_v2.run(context)
            if not isinstance(decision, TradingDecisionV2):
                raise TypeError("TradingDecisionV2 required")
            self._last_decision = decision
            if decision.action is not TradingActionV2.HOLD and not self._reasons():
                self._last_submission = s._generate_signal_if_configured(decision=decision, candle=normalized)
                self._last_plan = s.trade_plans[-1] if s.trade_plans else None
                self._risk = list(r.risk_evaluations)
                self._risk_vetoes += int(any(not x["approved"] for x in self._risk))
        # Diagnostic histories are bounded; authoritative trade ledgers are retained.
        for name in ("decisions", "trade_plans", "signals", "submission_results", "simulated_trades", "position_update_results"):
            getattr(s, name).clear()
        r.states.clear()
        r.risk_evaluations.clear()

    def shutdown(self):
        with self._lock:
            if self._paper is not None and not self._stopped:
                self._enabled = False
                self._stopped = True
                self._publish()
                try:
                    self._save()
                finally:
                    self._db.close()
