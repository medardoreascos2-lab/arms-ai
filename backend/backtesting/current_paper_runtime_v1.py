"""Opt-in current closed-bar PAPER coordinator. No broker-data/order adapter.

The replay runtime supplies durable ingestion and canonical accounting. Only
its finite-input boundary changes; strategy, costs, exits and risk do not.
"""
from copy import deepcopy
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from threading import RLock

from backend.backtesting.historical_accounting_v1 import HistoricalAccountingV1
from backend.backtesting.paper_research_v1 import PaperResearchSessionV1
from backend.backtesting.paper_runtime_v1 import PaperRuntimeV1
from backend.market_data.certified_bootstrap_v1 import CertifiedBootstrap
from backend.market_data.current_candle_authority_v1 import CurrentCandleAuthorityV1
from backend.market_data.session_state_v1 import SessionStateAuthorityV1, readiness_matrix
from backend.strategies.trading_strategy_v2 import TradingActionV2


_SUMMARY_COUNT_LIMIT = 2**63 - 1


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
        super().__init__(**kwargs)

        if self._paper is not None:
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
        if self.entry_authority is None or self._paper is None:
            return ["ENTRY_AUTHORITY_MISSING"]
        if self.health_eligible is None or not self.health_eligible():
            return ["CURRENT_PAPER_HEALTH_UNAVAILABLE"]
        runtime = self._paper.runtime
        return self.entry_authority.inspect(row=runtime.current,
            decision=self._last_decision,
            open_positions=len(runtime.lifecycle.get_active_positions()))

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
        # Only a completed canonical processing pass can contribute diagnostics.
        super()._process(observation)
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
                raise

    def _reasons(self):
        extra = self.gate.reasons()
        if self.entry_authority is None:
            extra.append("ENTRY_AUTHORITY_MISSING")
        if self.health_eligible is None or not self.health_eligible():
            extra.append("CURRENT_PAPER_HEALTH_UNAVAILABLE")
        return list(dict.fromkeys(super()._reasons() + extra))

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
