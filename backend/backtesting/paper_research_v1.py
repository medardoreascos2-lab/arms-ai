"""Explicit offline PAPER research; no default application execution wiring."""
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from threading import Lock

from backend.backtesting.historical_accounting_v1 import HistoricalAccountingV1, HistoricalCostsV1
from backend.backtesting.parameter_backtest_engine_factory_v2 import ParameterBacktestEngineFactoryV2


@dataclass(frozen=True)
class PaperResearchConfigV1:
    version: str
    mode: str
    boundary: float
    quality: float
    ema: int
    stop_loss: float
    take_profit: float
    fee_per_contract_side: float
    slippage_ticks_side: int
    live_execution_allowed: bool
    research_evidence_sha256: str

    def __post_init__(self):
        if (self.version != "sprint07r-paper-80.5-v1" or self.mode != "PAPER_RESEARCH"
                or self.live_execution_allowed is not False
                or (self.boundary,self.quality,self.ema,self.stop_loss,self.take_profit)!=(80.5,85,10,30,60)
                or (self.fee_per_contract_side,self.slippage_ticks_side)!=(5.0,2)
                or self.research_evidence_sha256 != "9e4542e57c9fc922cc0ad0fc3f104d072d24190f458260f842ff49fd15229855"):
            raise ValueError("only the certified Sprint07R PAPER research configuration is supported")

    @classmethod
    def load(cls, path):
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


class _ResearchConfluenceV1:
    """Same instance-local grade experiment as frozen V30; scores/gates unchanged."""
    def __init__(self, original, boundary):
        self.original, self.boundary = original, boundary

    def evaluate(self, **kwargs):
        result = self.original.evaluate(**kwargs)
        if result["score"] >= self.boundary:
            result = {**result, "grade": "A+"}
        return result


class PaperResearchSessionV1:
    """Explicit run command with atomic, read-only dashboard projections.

    GET never runs or marks the account. While replay runs, readers receive the
    last published state labeled RUNNING. A completed/failed run cannot restart.
    """
    def __init__(self, *, config, settings, policy, observations, contract):
        if type(config) is not PaperResearchConfigV1:
            raise TypeError("explicit certified PAPER research configuration required")
        self.config = config
        self._lock = Lock()
        engine = ParameterBacktestEngineFactoryV2(csv_path=None, settings=settings)(
            {"ema":config.ema,"stop_loss":config.stop_loss,"take_profit":config.take_profit})
        self.runtime = self.accounting_type(engine, policy=policy, observations=observations,
            contract=contract, costs=HistoricalCostsV1(config.fee_per_contract_side,config.slippage_ticks_side),
            strategy_version=config.version)
        strategy = self.runtime.session.strategy_runner_v2
        strategy.confluence_engine = _ResearchConfluenceV1(strategy.confluence_engine,config.boundary)
        self._snapshot = self._capture("READY")

    accounting_type = HistoricalAccountingV1

    def _capture(self, status):
        r = self.runtime
        decisions = r.session.decisions
        latest = None if not decisions else {**asdict(decisions[-1]), "action":decisions[-1].action.value}
        return {"dashboard_status":status,"mode":"PAPER_RESEARCH","live_execution_allowed":False,
                "configuration":asdict(self.config),"config_hash":r.config_hash,"contract":r.contract,
                "canonical_time":r.current.available_at.isoformat(),"processed_candles":r.index,
                "account_overview":r.account.get_state(),
                "active_simulated_positions":deepcopy(r.lifecycle.get_active_positions()),
                "latest_decision":latest,"latest_canonical_trade":deepcopy(r.completed[-1]) if r.completed else None,
                "completed_trades":len(r.completed),"journal_completed":len(r.journal.get_closed_trades()),
                "risk_vetoes":len({x["index"] for x in r.risk_evaluations if not x["approved"]})}

    def run(self):
        with self._lock:
            if self._snapshot["dashboard_status"] != "READY":
                raise RuntimeError("one explicit replay per fresh PAPER research session")
            self._snapshot["dashboard_status"] = "RUNNING"
        try:
            result = self.runtime.run()
            snapshot = self._capture("COMPLETED")
        except Exception:
            with self._lock:
                self._snapshot["dashboard_status"] = "FAILED"
            raise
        with self._lock:
            self._snapshot = snapshot
        return result

    def get_snapshot(self):
        with self._lock:
            return deepcopy(self._snapshot)
