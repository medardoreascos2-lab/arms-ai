"""Opt-in current closed-bar PAPER coordinator. No broker-data/order adapter.

The replay runtime supplies durable ingestion and canonical accounting. Only
its finite-input boundary changes; strategy, costs, exits and risk do not.
"""
from copy import deepcopy
from contextlib import closing
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import sqlite3
from threading import RLock

from backend.backtesting.historical_accounting_v1 import HistoricalAccountingV1
from backend.backtesting.paper_research_v1 import PaperResearchSessionV1
from backend.backtesting.paper_runtime_v1 import PaperRuntimeV1, _encode, _plain
from backend.market_data.certified_bootstrap_v1 import CertifiedBootstrap
from backend.market_data.current_candle_authority_v1 import CurrentCandleAuthorityV1
from backend.market_data.session_state_v1 import SessionStateAuthorityV1, readiness_matrix
from backend.strategies.trading_strategy_v2 import TradingActionV2


_SUMMARY_COUNT_LIMIT = 2**63 - 1
# This covers the existing 3,000-close multiday continuity test while keeping
# a finite hard limit. Exhaustion stops the next eligible observation before
# strategy or financial processing; evidence is never silently replaced.
MAX_DECISION_TRACE_RECORDS = 4096
MAX_DECISION_TRACE_READ = 100


def _empty_decision_summary():
    return dict(total_hold_decisions=0, total_buy_decisions=0,
                total_sell_decisions=0, max_confidence_observed=None,
                max_confluence_observed=None, plan_count=0, submission_count=0)


def _finite_diagnostic(value):
    if type(value) not in (int, float):
        return None
    try:
        return value if isfinite(value) else None
    except (OverflowError, ValueError):
        return None


def _diagnostic_plain(value):
    """Detach diagnostic values without making a nonfinite score a write fault."""
    value = _plain(value)
    if isinstance(value, dict):
        return {key: _diagnostic_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_diagnostic_plain(item) for item in value]
    if type(value) is float and not isfinite(value):
        return None
    return value


class _CurrentAccountingV1(HistoricalAccountingV1):
    version = "current-paper-accounting-sprint10-v1"
    pending = None

    def _next_observation(self):
        if self.pending is None:
            raise ValueError("no admitted closed candle")
        row, self.pending = self.pending, None
        return row

    def advance(self, candle):
        # Keep the frozen historical executor byte-identical. This boundary only
        # advances admitted chronology; existing AccountStateManagerV2 owns rollover.
        row = self._next_observation()
        if candle != self.session._normalize_candle(row.candle()):
            raise ValueError("candle differs from admitted current observation")
        self.current = row
        self.index += 1
        self.account.ensure_trading_day()
        if self.account.get_state()["trading_day"] != row.trading_date:
            raise ValueError("current trading date mismatch")

    def run(self):
        raise RuntimeError("current PAPER requires explicit closed-event delivery")

    def record_close(self, position):
        super().record_close(position)
        # The journal and completed list share this canonical evidence record.
        # Label its source; never calculate or book a second financial result.
        self.completed[-1].update(execution_kind="SIMULATED / PAPER",
                                  clock="CURRENT_PROVIDER_CLOSED_BAR", provider=self.current.provider)


class _CurrentSessionV1(PaperResearchSessionV1):
    accounting_type = _CurrentAccountingV1


class _CurrentRuntimeV1(PaperRuntimeV1):
    session_type = _CurrentSessionV1

    def __init__(
        self,
        *,
        gate,
        strategy_bootstrap=None,
        entry_authority=None,
        health_eligible=None,
        **kwargs,
    ):
        self.gate = gate
        self.entry_authority = entry_authority
        self.health_eligible = health_eligible
        self.strategy_bootstrap = None
        self.strategy_bootstrap_bar_count = 0
        self._session_decision_summary = _empty_decision_summary()
        self._trace_table_ready = False
        self._trace_limit = MAX_DECISION_TRACE_RECORDS
        self._pending_trace = None
        self._trace_in_process = False
        self._trace_entry_evaluations = []
        self._trace_entry_inspected = False
        self._trace_readiness_reasons = None
        super().__init__(**kwargs)

        if self._paper is not None:
            try:
                self._db.execute("""
                    CREATE TABLE decision_trace (
                        sequence INTEGER PRIMARY KEY,
                        event_id INTEGER NOT NULL UNIQUE,
                        fingerprint TEXT NOT NULL UNIQUE,
                        canonical_observation_id TEXT NOT NULL UNIQUE,
                        action TEXT NOT NULL CHECK(action IN ('HOLD','BUY','SELL')),
                        confidence REAL,
                        confluence REAL,
                        plan_present INTEGER NOT NULL CHECK(plan_present IN (0,1)),
                        submission_present INTEGER NOT NULL CHECK(submission_present IN (0,1)),
                        payload TEXT NOT NULL,
                        payload_sha256 TEXT NOT NULL
                    )
                """)
                self._db.commit()
                self._trace_table_ready = True
            except BaseException:
                self._fault = "RECOVERY_REQUIRED"
                self._enabled = False
                self._db.close()
                self._db = None
                raise
            self._install_current_submission_guard()

        # Existing namespaces are recovery evidence only.
        if (
            self._paper is not None
            and strategy_bootstrap is not None
        ):
            try:
                self._install_strategy_bootstrap(
                    strategy_bootstrap
                )
            except BaseException:
                self._fault = "RECOVERY_REQUIRED"
                self._enabled = False

                try:
                    self._publish()
                    self._save()
                finally:
                    if self._db is not None:
                        self._db.close()
                        self._db = None

                raise

    def _install_strategy_bootstrap(
        self,
        bootstrap,
    ):
        if (
            type(bootstrap)
            is not CertifiedBootstrap
            or not bootstrap.bars
        ):
            raise ValueError(
                "CERTIFIED_BOOTSTRAP_REQUIRED"
            )

        if self.strategy_bootstrap is not None:
            raise ValueError(
                "STRATEGY_BOOTSTRAP_REENTRY"
            )

        r = self._paper.runtime
        s = r.session

        if (
            self._cursor != 0
            or r.index != 0
            or s.candle_history
            or r.entries
            or r.completed
            or r.journal.trades
            or r.lifecycle.get_active_positions()
            or r.lifecycle.broker_connector_v2.get_fills()
        ):
            raise ValueError(
                "STRATEGY_BOOTSTRAP_NOT_FRESH"
            )

        candles = tuple(
            bar.candle()
            for bar
            in bootstrap.bars
        )

        if (
            candles[-1].timestamp
            >= r.current.canonical_timestamp
        ):
            raise ValueError(
                "STRATEGY_BOOTSTRAP_LIVE_ORDER"
            )

        account_before = deepcopy(
            r.account.capture_state()
        )

        calls_before = (
            s.strategy_runner_v2.calls
        )

        for candle in candles:
            normalized = (
                s._normalize_candle(
                    candle
                )
            )

            s.candle_history.append(
                normalized
            )

            del s.candle_history[
                :-s.analysis_window
            ]

            self._htf.update_completed(
                candle
            )

        if (
            s.strategy_runner_v2.calls
            != calls_before
        ):
            raise ValueError(
                "BOOTSTRAP_STRATEGY_EXECUTION"
            )

        if any(
            getattr(
                s,
                name,
            )
            for name in (
                "decisions",
                "trade_plans",
                "signals",
                "submission_results",
                "simulated_trades",
                "position_update_results",
            )
        ):
            raise ValueError(
                "BOOTSTRAP_EXECUTION_SIDE_EFFECT"
            )

        if (
            r.account.capture_state()
            != account_before
            or r.entries
            or r.completed
            or r.journal.trades
            or r.lifecycle.get_active_positions()
            or r.lifecycle.broker_connector_v2.get_fills()
        ):
            raise ValueError(
                "BOOTSTRAP_FINANCIAL_SIDE_EFFECT"
            )

        self.strategy_bootstrap = bootstrap

        self.strategy_bootstrap_bar_count = (
            len(
                bootstrap.bars
            )
        )

        # Bind the certified bootstrap into the durable runtime
        # configuration identity.  No financial owner is changed.
        self._identity = sha256(
            json.dumps(
                {
                    "runtime_identity":
                        self._identity,
                    "strategy_bootstrap_sha256":
                        bootstrap.sha256,
                    "strategy_bootstrap_bar_count":
                        self.strategy_bootstrap_bar_count,
                    "strategy_bootstrap_mode":
                        "NONEXECUTING_CONTEXT_ONLY",
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        self._publish()
        self._save()

    def _input_exhausted(self):
        return False

    def _install_current_submission_guard(self):
        """Keep the exact PAPER lifecycle object while adding only vetoes."""
        runtime = self._paper.runtime
        life = runtime.lifecycle
        original = life.submit_signal

        def submit_current(*, signal, order_type, risk_context, order_context):
            reasons = self._entry_reasons()
            if reasons:
                return {"accepted": False, "reason": reasons[0], "blocking_reasons": reasons,
                    "prepared_order": None, "execution": None, "position": None,
                    "active_position_id": None}
            context = dict(order_context)
            context["market_is_open"] = not self.gate.reasons()
            return original(signal=signal, order_type=order_type,
                risk_context=risk_context, order_context=context)

        self._current_submit = submit_current
        self._current_pre_submit = self._entry_reasons
        life.submit_signal = submit_current
        life.current_paper_pre_submit = self._current_pre_submit

    def _entry_reasons(self):
        inspected = False
        gates = {"health": dict(status="NOT_EVALUATED", reasons=[])}
        if self.entry_authority is None or self._paper is None:
            reasons = ["ENTRY_AUTHORITY_MISSING"]
        else:
            health = self.health_eligible is not None and self.health_eligible()
            gates["health"] = dict(status="PASS" if health else "BLOCKED",
                reasons=[] if health else ["CURRENT_PAPER_HEALTH_UNAVAILABLE"])
            if not health:
                reasons = ["CURRENT_PAPER_HEALTH_UNAVAILABLE"]
            else:
                runtime = self._paper.runtime
                inspected = True
                if self._trace_in_process:
                    self._trace_entry_inspected = True
                reasons = self.entry_authority.inspect(row=runtime.current,
                    decision=self._last_decision,
                    open_positions=len(runtime.lifecycle.get_active_positions()),
                    diagnostic=gates)
        if self._trace_in_process:
            self._trace_entry_evaluations.append(dict(
                blocking_reasons=list(reasons),
                entry_authority_inspected=inspected,
                infrastructure_gates=_diagnostic_plain(gates)))
        return reasons

    def _authority_reasons(self):
        reasons = super()._authority_reasons()
        if self._paper is not None and hasattr(self, "_current_submit"):
            life = self._paper.runtime.lifecycle
            if (life.submit_signal is not self._current_submit or
                    life.current_paper_pre_submit is not self._current_pre_submit):
                reasons.append("CURRENT_SUBMISSION_GUARD_CHANGED")
        return reasons

    def _validate_observation(self, observation):
        if observation is not self._paper.runtime.pending:
            raise ValueError("unadmitted current observation")

    def _can_analyze(self):
        r = self._paper.runtime

        return (
            len(
                r.session.candle_history
            )
            >= r.engine.minimum_candles
            and not self.gate.reasons()
        )

    def _process(self, observation):
        # The limit is checked before any strategy, account, or execution work.
        # The generic ingest has already durably marked this event INFLIGHT.
        if self._db.execute("SELECT count(*) FROM decision_trace").fetchone()[0] >= self._trace_limit:
            raise RuntimeError("DECISION_TRACE_CAPACITY_REACHED")
        self._trace_entry_evaluations = []
        self._trace_entry_inspected = False
        self._trace_readiness_reasons = None
        self._trace_in_process = True
        try:
            super()._process(observation)
        finally:
            self._trace_in_process = False
        decision = self._last_decision
        if decision is None:
            return
        summary = self._session_decision_summary
        action_key = {
            TradingActionV2.HOLD: "total_hold_decisions",
            TradingActionV2.BUY: "total_buy_decisions",
            TradingActionV2.SELL: "total_sell_decisions",
        }.get(decision.action)
        if action_key is not None:
            summary[action_key] = min(summary[action_key] + 1, _SUMMARY_COUNT_LIMIT)
        confidence = _finite_diagnostic(decision.confidence)
        if confidence is not None:
            current = summary["max_confidence_observed"]
            summary["max_confidence_observed"] = confidence if current is None else max(current, confidence)
        metadata = decision.metadata
        confluence = _finite_diagnostic(metadata.get("confluence_score") if isinstance(metadata, dict) else None)
        if confluence is not None:
            current = summary["max_confluence_observed"]
            summary["max_confluence_observed"] = confluence if current is None else max(current, confluence)
        if self._last_plan is not None:
            summary["plan_count"] = min(summary["plan_count"] + 1, _SUMMARY_COUNT_LIMIT)
        if self._last_submission is not None:
            summary["submission_count"] = min(summary["submission_count"] + 1, _SUMMARY_COUNT_LIMIT)
        self._pending_trace = self._decision_trace(observation, decision)

    def _decision_trace(self, observation, decision):
        metadata = decision.metadata if isinstance(decision.metadata, dict) else {}
        evidence = _diagnostic_plain(self._strategy_evidence)
        quality = evidence.get("quality") or {}
        confluence = evidence.get("confluence") or {}
        identity = dict(source_sha256=observation.source_sha256,
            source_file=observation.source_file, source_row=observation.source_row,
            raw_row_sha256=sha256(observation.raw_row.encode("utf-8")).hexdigest(),
            event_id=observation.event_id,
            canonical_timestamp=observation.canonical_timestamp.isoformat(),
            trading_date=observation.trading_date,
            provider=observation.provider,
            instrument=self.gate.contract.instrument,
            contract=observation.contract)
        canonical_id = sha256(_encode(identity).encode("utf-8")).hexdigest()
        if self._trace_entry_inspected:
            gate_status = "EVALUATED"
        elif self._trace_entry_evaluations:
            gate_status = "NOT_EVALUATED_ENTRY_AUTHORITY_SKIPPED"
        elif decision.action is TradingActionV2.HOLD:
            gate_status = "NOT_EVALUATED_NON_ACTIONABLE_DECISION"
        elif self._trace_readiness_reasons:
            gate_status = "NOT_EVALUATED_READINESS_BLOCKED"
        else:
            gate_status = "NOT_EVALUATED_UPSTREAM_BLOCKED"
        return dict(canonical_observation_id=canonical_id,
            event_fingerprint=sha256(repr(observation).encode()).hexdigest(),
            observation=identity, action=decision.action.value,
            confidence=_finite_diagnostic(decision.confidence),
            decision_reason=decision.reason,
            decision_metadata=_diagnostic_plain(metadata),
            trade_quality_score=quality.get("score"),
            trade_quality_grade=None,
            trade_quality_grade_status="NOT_PRODUCED_BY_QUALITY_ENGINE",
            trade_quality_reasons=quality.get("reasons", metadata.get("trade_quality_reasons", [])),
            confluence_score=_finite_diagnostic(metadata.get("confluence_score")),
            confluence_engine_score=_finite_diagnostic(confluence.get("score")),
            confluence_grade=confluence.get("grade", metadata.get("grade")),
            confluence_approved=confluence.get("approved"),
            confluence_status=confluence.get("status", "OBSERVED" if confluence else "NOT_OBSERVED"),
            strategy_evidence=evidence,
            entry_gate_status=gate_status,
            entry_gate_evaluations=deepcopy(self._trace_entry_evaluations),
            news_l1_spread_status=("EVALUATED_SEE_ENTRY_GATE_EVALUATIONS"
                if self._trace_entry_inspected else "NOT_EVALUATED"),
            progression_readiness_reasons=(deepcopy(self._trace_readiness_reasons)
                if self._trace_readiness_reasons is not None else "NOT_EVALUATED"))

    def _save(self):
        if not self._trace_table_ready:
            return super()._save()
        trace = self._pending_trace
        if trace is not None:
            sequence = self._db.execute("SELECT count(*) FROM decision_trace").fetchone()[0] + 1
            if sequence > self._trace_limit:
                raise RuntimeError("DECISION_TRACE_CAPACITY_REACHED")
            plan = deepcopy(self._snapshot["plan"])
            submission = deepcopy(self._snapshot["submission"])
            risk = deepcopy(self._snapshot["risk_evaluation"])
            committed = dict(trace, sequence=sequence, event_id=self._cursor - 1,
                plan_present=plan is not None, plan=plan,
                submission_present=submission is not None, submission=submission,
                submission_outcome=({key: submission.get(key) for key in
                    ("accepted", "reason", "blocking_reasons")}
                    if isinstance(submission, dict) else "NOT_EVALUATED"),
                prepared_order_present=(submission.get("prepared_order") is not None
                    if isinstance(submission, dict) else False),
                execution_present=(submission.get("execution") is not None
                    if isinstance(submission, dict) else False),
                risk_status="EVALUATED" if risk else "NOT_EVALUATED",
                risk_evaluation=risk if risk else "NOT_EVALUATED")
            payload = _encode(committed)
            self._db.execute("INSERT INTO decision_trace VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (sequence, committed["event_id"], trace["event_fingerprint"],
                 trace["canonical_observation_id"], trace["action"],
                 trace["confidence"], trace["confluence_score"],
                 int(committed["plan_present"]), int(committed["submission_present"]), payload,
                 sha256(payload.encode("utf-8")).hexdigest()))
        counts = dict(self._db.execute(
            "SELECT action,count(*) FROM decision_trace GROUP BY action").fetchall())
        maxima = self._db.execute("SELECT max(confidence),max(confluence),"
            "sum(plan_present),sum(submission_present) FROM decision_trace").fetchone()
        summary = self._session_decision_summary
        if any(counts.get(action, 0) != summary[key] for action, key in (
                ("HOLD", "total_hold_decisions"), ("BUY", "total_buy_decisions"),
                ("SELL", "total_sell_decisions"))) or (
                (maxima[0], maxima[1], maxima[2] or 0, maxima[3] or 0) !=
                (summary["max_confidence_observed"], summary["max_confluence_observed"],
                 summary["plan_count"], summary["submission_count"])):
            raise RuntimeError("DECISION_TRACE_SUMMARY_MISMATCH")
        super()._save()  # Same transaction as event completion and journal.
        self._pending_trace = None

    def ingest(self, observation, *, received_at):
        with self._lock:
            committed = self._session_decision_summary.copy()
            try:
                return super().ingest(observation, received_at=received_at)
            except BaseException:
                # Generic ingest rolls back the event/checkpoint transaction.
                # Keep the published diagnostic aligned with that last commit.
                self._session_decision_summary = committed
                self._snapshot["session_decision_summary"] = deepcopy(committed)
                self._pending_trace = None
                raise

    def _reasons(self):
        extra = self.gate.reasons()
        if self.entry_authority is None:
            extra.append("ENTRY_AUTHORITY_MISSING")
        if self.health_eligible is None or not self.health_eligible():
            extra.append("CURRENT_PAPER_HEALTH_UNAVAILABLE")
        reasons = list(dict.fromkeys(super()._reasons() + extra))
        if self._trace_in_process and self._last_decision is not None:
            self._trace_readiness_reasons = list(reasons)
        return reasons

    def get_decision_trace(self, *, limit=MAX_DECISION_TRACE_READ):
        """Detached, bounded, committed evidence; never resumes a namespace."""
        if type(limit) is not int or not 1 <= limit <= MAX_DECISION_TRACE_READ:
            raise ValueError("DECISION_TRACE_READ_LIMIT")
        with self._lock:
            with closing(sqlite3.connect(self._path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
                present = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='decision_trace'").fetchone()
                if not present:
                    return dict(status="UNAVAILABLE_LEGACY", records=[], total=0,
                        operational_state_restored=False)
                completed = ("FROM decision_trace AS trace JOIN events AS event "
                    "ON event.id=trace.event_id AND event.fingerprint=trace.fingerprint "
                    "WHERE event.phase='COMPLETED'")
                total = db.execute("SELECT count(*) " + completed).fetchone()[0]
                records = []
                for payload, digest in db.execute(
                        "SELECT trace.payload,trace.payload_sha256 " + completed +
                        " ORDER BY trace.sequence DESC LIMIT ?", (limit,)):
                    if sha256(payload.encode("utf-8")).hexdigest() != digest:
                        return dict(status="UNREADABLE_RECONCILIATION_REQUIRED",
                            records=[], total=total, operational_state_restored=False)
                    records.append(json.loads(payload))
                return dict(status="COMMITTED_EVIDENCE", records=records, total=total,
                    operational_state_restored=False)

    def _publish(self):
        super()._publish()
        # A malformed diagnostic score must not make checkpoint JSON fail.
        # Preserve the canonical decision object; omit only the invalid score
        # from its detached, published representation.
        latest = self._snapshot.get("latest_decision")
        metadata = latest.get("metadata") if isinstance(latest, dict) else None
        if isinstance(metadata, dict) and "confluence_score" in metadata:
            score = metadata["confluence_score"]
            if type(score) in (int, float) and _finite_diagnostic(score) is None:
                del metadata["confluence_score"]

        self._snapshot.update(
            session_decision_summary=deepcopy(self._session_decision_summary),
            mode="CURRENT_MARKET_PAPER",
            clock="CURRENT_PROVIDER_CLOSED_BAR",
            execution_kind="SIMULATED / PAPER",
            feed_contract_sha256=self.gate.digest,
            strategy_bootstrap_mode=(
                "NONEXECUTING_CONTEXT_ONLY"
                if self.strategy_bootstrap
                is not None
                else "NONE"
            ),
            strategy_bootstrap_sha256=(
                self.strategy_bootstrap.sha256
                if self.strategy_bootstrap
                is not None
                else None
            ),
            strategy_bootstrap_bar_count=(
                self.strategy_bootstrap_bar_count
            ),
            strategy_bootstrap_execution_authority=False,
        )

    def step(self):
        raise RuntimeError("current PAPER has no replay step")


class CurrentPaperServiceV1:
    """Single serialized feed authority, lazily created isolated PAPER account.

    No account exists before the first validated close. Existing namespaces
    expose recovery evidence only. Disconnection never synthesizes prices or
    closes positions; subsequent proven valid closes retain canonical exits.
    """
    def __init__(self, *, gate, config, settings, state_path, initialization_policy,
                 entry_authority=None):
        if type(gate) is not CurrentCandleAuthorityV1:
            raise TypeError("canonical current candle authority required")
        if initialization_policy != "NEW_ISOLATED_PAPER_ACCOUNT":
            raise ValueError("explicit new isolated account policy required")
        if gate.maximum_age != settings.maximum_quote_age_seconds:
            raise ValueError("feed/runtime freshness limits must agree")
        self.gate = gate
        self._lock = RLock()
        self._runtime = None
        self._stopped = False
        self._strategy_bootstrap = None
        self.entry_authority = entry_authority
        self._health_at = None
        self._health_live = False
        self._arguments = dict(mode="PAPER_RESEARCH", config=config, settings=settings,
            policy=gate, contract=gate.contract.contract, state_path=state_path,
            initialization_policy=initialization_policy, entry_authority=entry_authority,
            health_eligible=self.health_eligible)
        if Path(state_path).exists():
            self._runtime = _CurrentRuntimeV1(gate=gate, observations=(), **self._arguments)

    def install_strategy_bootstrap(
        self,
        bootstrap,
    ):
        """Install one certified nonexecuting strategy warm-up.

        This method never creates an account/runtime and never evaluates
        strategy, risk, lifecycle or execution.
        """
        with self._lock:
            if (
                type(bootstrap)
                is not CertifiedBootstrap
                or not bootstrap.bars
            ):
                raise TypeError(
                    "exact nonempty CertifiedBootstrap required"
                )

            if (
                self._stopped
                or self._runtime is not None
                or self.gate.connected
                or self.gate.last_sequence
                is not None
                or self._strategy_bootstrap
                is not None
            ):
                raise RuntimeError(
                    "STRATEGY_BOOTSTRAP_INSTALL_NOT_FRESH"
                )

            self._strategy_bootstrap = (
                bootstrap
            )

            return self.get_snapshot()

    def connection(self, connected):
        with self._lock:
            if self._stopped:
                raise RuntimeError("STOPPED")
            self.gate.connection(connected)
            if not connected:
                self.invalidate_health()
            return self.get_snapshot()

    def health_eligible(self):
        with self._lock:
            if not self._health_live or self._health_at is None or self._stopped:
                return False
            try:
                now = self.gate.clock()
                age = (now - self._health_at).total_seconds()
                session = SessionStateAuthorityV1(self.gate.market_hours).resolve(
                    now, last_closed=self.gate.last_closed)
                return (0 <= age <= 2 and session.state == "OPEN" and self.gate.connected
                    and not self.gate.reconnecting and not self.gate.fault)
            except (ValueError, TypeError, OverflowError):
                return False

    def publish_health(self, *, coordinator, worker_alive):
        """Worker-owned, cached attestation; never arms PAPER."""
        with self._lock:
            bridge = coordinator.get("bridge") or {}
            live = (worker_alive and coordinator.get("status") == "LIVE"
                and coordinator.get("source_adapter_status") == "LIVE_TAIL"
                and bridge.get("status") == "LIVE" and self.gate.connected
                and not self.gate.fault
                and not self._stopped)
            if not live:
                self.invalidate_health()
                return False
            self._health_at = self.gate.clock()
            self._health_live = True
            if not self.health_eligible():
                self.invalidate_health()
                return False
            return True

    def invalidate_health(self):
        with self._lock:
            self._health_live = False
            self._health_at = None
            if self._runtime is not None and self._runtime._enabled:
                try:
                    self._runtime.control("disable")
                except (ValueError, RuntimeError, OSError):
                    self._runtime._enabled = False
                    self._runtime._fault = "RECOVERY_REQUIRED"
                    raise

    def ingest(self, event):
        with self._lock:
            if self._stopped or (self._runtime is not None and self._runtime._paper is None):
                raise RuntimeError("STOPPED or RECOVERY_REQUIRED")
            row = self.gate.admit(event)
            if row is None:
                return self.get_snapshot()
            if self.entry_authority is not None:
                self.entry_authority.observe(row)
            if self._runtime is None:
                self._runtime = _CurrentRuntimeV1(
                    gate=self.gate,
                    observations=(row,),
                    strategy_bootstrap=(
                        self._strategy_bootstrap
                    ),
                    **self._arguments,
                )
            self._runtime._paper.runtime.pending = row
            self._runtime.ingest(row, received_at=row.received_at)
            return self.get_snapshot()

    def get_snapshot(self):
        with self._lock:
            g = self.gate
            snapshot = (self._runtime.get_snapshot() if self._runtime is not None else
                        dict(account_overview=None, paper_ready=False, config_hash=g.digest,
                             readiness_reasons=["AWAITING_MARKET_DATA", "PAPER_DISABLED"],
                             session_decision_summary=_empty_decision_summary()))
            reasons = list(dict.fromkeys(snapshot["readiness_reasons"] + g.reasons()
                                         + (["STOPPED"] if self._stopped else [])))
            if not self.health_eligible():
                reasons.append("CURRENT_PAPER_HEALTH_UNAVAILABLE")
            if self.entry_authority is None:
                reasons.append("ENTRY_AUTHORITY_MISSING")
            reasons = list(dict.fromkeys(reasons))
            snapshot.update(mode="CURRENT_MARKET_PAPER", execution_kind="SIMULATED / PAPER",
                clock="CURRENT_PROVIDER_CLOSED_BAR", live_execution_allowed=False,
                strategy_bootstrap_mode=(
                    "NONEXECUTING_CONTEXT_ONLY"
                    if self._strategy_bootstrap is not None
                    else "NONE"
                ),
                strategy_bootstrap_sha256=(
                    self._strategy_bootstrap.sha256
                    if self._strategy_bootstrap is not None
                    else None
                ),
                strategy_bootstrap_bar_count=(
                    len(self._strategy_bootstrap.bars)
                    if self._strategy_bootstrap is not None
                    else 0
                ),
                strategy_bootstrap_execution_authority=False,
                paper_ready=not reasons, readiness_reasons=reasons,
                dashboard_status="PAPER_READY" if not reasons else "BLOCKED",
                recovery_required="RECOVERY_REQUIRED" in reasons,
                feed_contract_sha256=g.digest,
                market_data=dict(provider=g.contract.provider, contract=g.contract.contract,
                    instrument=g.contract.instrument, tick_size=g.contract.tick_size,
                    point_value=g.contract.point_value, trading_hours_template=g.contract.trading_hours_template,
                    source_timezone=g.contract.source_timezone, bar_label=g.contract.bar_label,
                    fixture=g.contract.fixture, connected=g.connected, status=g.last_status,
                    version=g.version, closed_candles=g.closed_count, duplicates=g.duplicate_count,
                    last_raw_event_time=g.last_event_time.isoformat() if g.last_event_time else None,
                    last_received_time=g.last_received.isoformat() if g.last_received else None,
                    last_closed_1m_time=g.last_closed.isoformat() if g.last_closed else None,
                    data_age_seconds=g.age_seconds()))
            session = SessionStateAuthorityV1(g.market_hours).resolve(g.clock(), last_closed=g.last_closed)
            age = g.age_seconds()
            snapshot["session_state"] = session.snapshot()
            snapshot["provider_state"] = "CONNECTED" if g.connected else "DISCONNECTED"
            snapshot["data_freshness"] = "FRESH" if age is not None and 0 <= age <= g.maximum_age else "STALE_OR_MISSING"
            snapshot["session_readiness"] = readiness_matrix(session, snapshot["provider_state"],
                fresh=snapshot["data_freshness"] == "FRESH", recovery_clear=not snapshot["recovery_required"],
                risk_ready=not reasons, enabled=not reasons)
            snapshot["sim_eligibility_status"] = "UNKNOWN_ACCOUNT_INELIGIBLE"
            snapshot["sim_discovery_status"] = "NOT_IMPLEMENTED_AUTHORITY_UNPROVEN"
            snapshot["sim_classification_status"] = "UNKNOWN"
            snapshot["sim_binding_status"] = "NOT_CONFIGURED"
            snapshot["sim_execution_authority"] = "DISABLED"
            snapshot["htf_current_session"] = {
                tf: sum(bar.timestamp >= session.segment_start for bar in self._runtime._htf.history(tf))
                if session.segment_start and self._runtime and hasattr(self._runtime, "_htf") else 0
                for tf in ("15m", "1h")}
            return deepcopy(snapshot)

    def get_decision_trace(self, *, limit=MAX_DECISION_TRACE_READ):
        if type(limit) is not int or not 1 <= limit <= MAX_DECISION_TRACE_READ:
            raise ValueError("DECISION_TRACE_READ_LIMIT")
        with self._lock:
            if self._runtime is None:
                return dict(status="AWAITING_MARKET_DATA", records=[], total=0,
                    operational_state_restored=False)
            return self._runtime.get_decision_trace(limit=limit)

    def control(self, command):
        with self._lock:
            if self._runtime is None or self._stopped:
                raise RuntimeError("AWAITING_MARKET_DATA or STOPPED")
            if self.gate.fault:
                raise RuntimeError("RECOVERY_REQUIRED")
            if command == "enable" and self.gate.contract.fixture and self.entry_authority is None:
                # Legacy synthetic protocol smoke has no execution authority.
                # Keep its in-process enable attempt inert.
                return self.get_snapshot()
            if command == "enable" and (self.entry_authority is None or
                    not self.health_eligible() or self.gate.reasons()):
                raise RuntimeError("CURRENT_PAPER_HEALTH_OR_AUTHORITY_UNAVAILABLE")
            self._runtime.control(command)
            return self.get_snapshot()

    def shutdown(self):
        with self._lock:
            self.invalidate_health()
            self._stopped = True
            if self._runtime is not None:
                self._runtime.shutdown()
