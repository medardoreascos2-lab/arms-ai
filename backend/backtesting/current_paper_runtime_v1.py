"""Opt-in current closed-bar PAPER coordinator. No broker-data/order adapter.

The replay runtime supplies durable ingestion and canonical accounting. Only
its finite-input boundary changes; strategy, costs, exits and risk do not.
"""
from copy import deepcopy
from pathlib import Path
from threading import RLock

from backend.backtesting.historical_accounting_v1 import HistoricalAccountingV1
from backend.backtesting.paper_research_v1 import PaperResearchSessionV1
from backend.backtesting.paper_runtime_v1 import PaperRuntimeV1
from backend.market_data.current_candle_authority_v1 import CurrentCandleAuthorityV1


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

    def __init__(self, *, gate, **kwargs):
        self.gate = gate
        super().__init__(**kwargs)

    def _input_exhausted(self):
        return False

    def _validate_observation(self, observation):
        if observation is not self._paper.runtime.pending:
            raise ValueError("unadmitted current observation")

    def _can_analyze(self):
        return self._paper.runtime.index >= self._paper.runtime.engine.minimum_candles

    def _reasons(self):
        return list(dict.fromkeys(super()._reasons() + self.gate.reasons()))

    def _publish(self):
        super()._publish()
        self._snapshot.update(mode="CURRENT_MARKET_PAPER", clock="CURRENT_PROVIDER_CLOSED_BAR",
                              execution_kind="SIMULATED / PAPER", feed_contract_sha256=self.gate.digest)

    def step(self):
        raise RuntimeError("current PAPER has no replay step")


class CurrentPaperServiceV1:
    """Single serialized feed authority, lazily created isolated PAPER account.

    No account exists before the first validated close. Existing namespaces
    expose recovery evidence only. Disconnection never synthesizes prices or
    closes positions; subsequent proven valid closes retain canonical exits.
    """
    def __init__(self, *, gate, config, settings, state_path, initialization_policy):
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
        self._arguments = dict(mode="PAPER_RESEARCH", config=config, settings=settings,
            policy=gate, contract=gate.contract.contract, state_path=state_path,
            initialization_policy=initialization_policy)
        if Path(state_path).exists():
            self._runtime = _CurrentRuntimeV1(gate=gate, observations=(), **self._arguments)

    def connection(self, connected):
        with self._lock:
            if self._stopped:
                raise RuntimeError("STOPPED")
            self.gate.connection(connected)
            return self.get_snapshot()

    def ingest(self, event):
        with self._lock:
            if self._stopped or (self._runtime is not None and self._runtime._paper is None):
                raise RuntimeError("STOPPED or RECOVERY_REQUIRED")
            row = self.gate.admit(event)
            if row is None:
                return self.get_snapshot()
            if self._runtime is None:
                self._runtime = _CurrentRuntimeV1(gate=self.gate, observations=(row,), **self._arguments)
            self._runtime._paper.runtime.pending = row
            self._runtime.ingest(row, received_at=row.received_at)
            return self.get_snapshot()

    def get_snapshot(self):
        with self._lock:
            g = self.gate
            snapshot = (self._runtime.get_snapshot() if self._runtime is not None else
                        dict(account_overview=None, paper_ready=False, config_hash=g.digest,
                             readiness_reasons=["AWAITING_MARKET_DATA", "PAPER_DISABLED"]))
            reasons = list(dict.fromkeys(snapshot["readiness_reasons"] + g.reasons()
                                         + (["STOPPED"] if self._stopped else [])))
            snapshot.update(mode="CURRENT_MARKET_PAPER", execution_kind="SIMULATED / PAPER",
                clock="CURRENT_PROVIDER_CLOSED_BAR", live_execution_allowed=False,
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
            return deepcopy(snapshot)

    def control(self, command):
        with self._lock:
            if self._runtime is None or self._stopped:
                raise RuntimeError("AWAITING_MARKET_DATA or STOPPED")
            if self.gate.fault:
                raise RuntimeError("RECOVERY_REQUIRED")
            self._runtime.control(command)
            return self.get_snapshot()

    def shutdown(self):
        with self._lock:
            self._stopped = True
            if self._runtime is not None:
                self._runtime.shutdown()
