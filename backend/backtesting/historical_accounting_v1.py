"""Explicit, isolated historical PAPER accounting; never wired into LIVE.

The inherited session still owns strategy/HTF chronology and submission gates.
Only this composition replaces future-scanning simulation and close-only marks.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite

from backend.account.account_state_manager_v2 import AccountStateManagerV2
from backend.backtesting.backtest_session_v2 import BacktestSessionV2
from backend.connectors.paper_broker_connector_v2 import PaperBrokerConnectorV2
from backend.execution.position_manager_v2 import PositionManagerV2
from backend.execution.risk_manager_v2 import RiskManagerV2
from backend.execution.trade_execution_simulator_v2 import SimulatedTrade
from backend.journal.trade_journal_v2 import TradeJournalV2
from backend.portfolio.portfolio_manager_v2 import PortfolioManagerV2
from backend.risk.risk_compatibility_adapter_v2 import RiskCompatibilityAdapterV2, RiskCompatibilityResultV2
from backend.services.trade_lifecycle_service_v2 import TradeLifecycleServiceV2


@dataclass(frozen=True)
class HistoricalCostsV1:
    """Research assumptions, not a broker fee schedule. Fees booked on close."""
    fee_per_contract_side: float = 0.0
    slippage_ticks_side: int = 0

    def __post_init__(self):
        if (not isfinite(self.fee_per_contract_side) or self.fee_per_contract_side < 0
                or type(self.slippage_ticks_side) is not int or self.slippage_ticks_side < 0):
            raise ValueError("finite nonnegative fees and integer slippage required")

    @property
    def slippage_points(self):
        return self.slippage_ticks_side * .25

    @property
    def roundtrip_fee(self):
        return self.fee_per_contract_side * 2


class _HistoricalPositionManager(PositionManagerV2):
    def __init__(self, runtime):
        super().__init__(point_value=20.0)
        self.runtime = runtime

    def update_position(self, *, position, current_price):
        r = self.runtime
        bar = r.current.candle()
        if position["status"] != "OPEN" or position["symbol"] != "NQ":
            raise ValueError("only open NQ historical positions are supported")
        if current_price != bar.close:
            raise ValueError("historical marking must use the current eligible bar")
        long = position["direction"] == "LONG"
        stop, target = position["stop_loss"], position["take_profit"]
        hit_stop = bar.low <= stop if long else bar.high >= stop
        hit_target = bar.high >= target if long else bar.low <= target
        reason = "STOP_LOSS" if hit_stop else "TAKE_PROFIT" if hit_target else None
        sign = 1 if long else -1
        price = stop if hit_stop else target if hit_target else bar.close
        fill = price - sign * r.costs.slippage_points if reason else price
        points = sign * (fill - position["entry_price"])
        gross = round(points * position["quantity"] * position["point_value"], 10)
        result = dict(position, current_price=fill, unrealized_points=points)
        if reason:
            fees = r.costs.roundtrip_fee * position["quantity"]
            result.update(status="CLOSED", exit_price=fill, close_reason=reason,
                          gross_pnl=gross, execution_fees=fees, realized_pnl=round(gross-fees, 10),
                          total_pnl=round(gross-fees, 10), unrealized_pnl=0.0,
                          trigger_price=price, closed_at=r.current.available_at)
        else:
            result.update(unrealized_pnl=gross)
        return result


class _HistoricalJournal(TradeJournalV2):
    def __init__(self, runtime):
        super().__init__()
        self.runtime = runtime

    def record_open_trade(self, trade):
        record = super().record_open_trade(trade)
        record.created_at = self.runtime.current.available_at
        return record

    def close_trade(self, *args, **kwargs):
        kwargs["exit_time"] = self.runtime.current.available_at
        return super().close_trade(*args, **kwargs)


class _HistoricalRiskManager(RiskManagerV2):
    def __init__(self, original, runtime):
        super().__init__(position_sizing_engine=original.position_sizing_engine,
                         maximum_daily_loss=original.maximum_daily_loss,
                         maximum_total_drawdown=original.maximum_total_drawdown,
                         maximum_contracts=original.maximum_contracts,
                         maximum_open_positions=original.maximum_open_positions,
                         contract_limit_resolver=original.contract_limit_resolver)
        self.runtime = runtime

    def evaluate(self, **kwargs):
        r = self.runtime
        # Adverse entry/stop-exit slippage and fees consume the existing budget.
        # No risk limit, sizing formula or policy is replaced.
        kwargs.update(r.risk_context())
        kwargs["stop_points"] += 2*r.costs.slippage_points + r.costs.roundtrip_fee/20.0
        result = super().evaluate(**kwargs)
        r.risk_evaluations.append({"index": r.index, "inputs": dict(kwargs),
                                   "approved": result["approved"],
                                   "reasons": list(result["blocking_reasons"])})
        return result


class _HistoricalRiskAdapter(RiskCompatibilityAdapterV2):
    def evaluate(self, **kwargs):
        r = self.risk_manager.runtime
        if r.account.get_state()["trading_blocked"]:
            r.risk_evaluations.append({"index": r.index, "inputs": r.risk_context(),
                                       "approved": False, "reasons": ["account_trading_blocked"]})
            return RiskCompatibilityResultV2(False, 0, 0.0, "account_trading_blocked")
        return super().evaluate(**kwargs)


class _HistoricalSession(BacktestSessionV2):
    def _update_active_position_if_configured(self, *, candle):
        r = self.historical_accounting
        r.advance(candle)
        previous = self.active_position_id
        super()._update_active_position_if_configured(candle=candle)
        if previous and self.active_position_id is None:
            p = self.position_update_results[-1]["position"]
            r.record_close(p)
            self.simulated_trades.append(SimulatedTrade(
                symbol=p["symbol"], direction="BUY" if p["direction"] == "LONG" else "SELL",
                entry=p["entry_price"], stop_loss=p["stop_loss"], take_profit=p["take_profit"],
                contracts=p["quantity"], risk_amount=abs(p["entry_price"]-p["stop_loss"])*p["quantity"]*p["point_value"],
                status="WIN" if p["realized_pnl"] > 0 else "LOSS" if p["realized_pnl"] < 0 else "BREAKEVEN",
                pnl=p["realized_pnl"], reasoning=[p["close_reason"], "CANONICAL_HISTORICAL_REALIZATION"]))
        r.capture_state()

    def _generate_signal_if_configured(self, *, decision, candle):
        r = self.historical_accounting
        self.signal_risk_context = r.risk_context()
        result = super()._generate_signal_if_configured(decision=decision, candle=candle)
        if isinstance(result, dict) and result.get("accepted") is True:
            position = result["position"]
            r.entries[position["position_id"]] = {
                "entry_index": r.index, "planned_entry": candle["close"],
                "entry_time": r.current.available_at.isoformat(),
                "entry_trading_date": r.current.trading_date,
                "entry_source_row": r.current.source_row,
                "score": decision.metadata.get("confluence_score"),
            }
        r.capture_state()
        return result

    def _execute_trade_if_configured(self, **kwargs):
        # Accepted lifecycle fill is the sole entry. No second execution path.
        return None


class HistoricalAccountingV1:
    """One fresh NQ segment with existing gates and one realized-account truth."""
    version = "historical-accounting-sprint07r-v1"

    def __init__(self, engine, *, policy, observations, contract, costs=None, strategy_version):
        rows = tuple(observations)
        policy.validate_segment(rows, contract=contract)
        self.rows = tuple(r for r in rows if r.strategy_context_eligible
                          and r.execution_price_eligible and r.session_accounting_eligible)
        if not self.rows:
            raise ValueError("no eligible observations")
        old = engine.pipeline.pipeline.backtest_session_v2
        life = old.signal_submission_target_v2
        if old._has_run or type(life) is not TradeLifecycleServiceV2 or life.get_active_positions():
            raise ValueError("fresh production lifecycle required")
        if (life.execution_manager.execution_mode != "PAPER"
                or type(life.broker_connector_v2) is not PaperBrokerConnectorV2
                or old.backtest_runner_v2.replay_market_data_bridge_v2.market_data_hub_v2 is not None):
            raise ValueError("isolated offline PAPER composition required")
        if life.portfolio_manager_v2 is not None or life.trade_journal_v2 is not None:
            raise ValueError("existing financial bindings cannot be replaced")
        if not strategy_version:
            raise ValueError("strategy/configuration identity required")
        self.engine, self.contract, self.lifecycle = engine, contract, life
        self.costs = costs or HistoricalCostsV1()
        self.strategy_version = strategy_version
        self.index, self.current = 0, self.rows[0]
        self.entries, self.completed, self.risk_evaluations, self.states = {}, [], [], []
        profile = old.account_config.get_active_account()
        self.risk_percent = float(profile.risk_percent)
        self.account = AccountStateManagerV2(starting_balance=float(profile.account_size),
            maximum_daily_loss=profile.daily_loss_limit, maximum_total_drawdown=profile.max_drawdown,
            profit_target=profile.profit_target, account_stage=profile.account_stage,
            clock=lambda: self.current.available_at)
        self.portfolio = PortfolioManagerV2(starting_balance=float(profile.account_size), account_state_manager_v2=self.account)
        self.journal = _HistoricalJournal(self)
        life.portfolio_manager_v2, life.trade_journal_v2 = self.portfolio, self.journal
        life.position_manager = _HistoricalPositionManager(self)
        life.paper_execution_engine.slippage_points = self.costs.slippage_points
        life.risk_manager_v2 = _HistoricalRiskManager(life.risk_manager_v2, self)
        config = {"version": self.version, "strategy": strategy_version, "contract": contract,
                  "source_sha256": self.rows[0].source_sha256, "calendar_sha256": policy.digest,
                  "account": self.account.capture_state(), "risk_percent": self.risk_percent,
                  "costs": self.costs.__dict__}
        self.config_hash = sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
        self.session = _HistoricalSession(backtest_runner_v2=old.backtest_runner_v2,
            strategy_runner_v2=old.strategy_runner_v2, trade_executor_v2=None,
            backtest_trade_plan_adapter_v2=old.backtest_trade_plan_adapter_v2,
            signal_generator_v2=old.signal_generator_v2, signal_submission_target_v2=life,
            signal_order_type=old.signal_order_type, signal_risk_context=self.risk_context(),
            signal_order_context=old.signal_order_context, analysis_window=old.analysis_window)
        self.session.historical_accounting = self
        self.session.risk_pipeline = _HistoricalRiskAdapter(risk_manager=life.risk_manager_v2)
        engine.pipeline.pipeline.backtest_session_v2 = self.session
        engine.initial_balance = float(profile.account_size)

    def risk_context(self):
        s = self.account.get_state()
        return {"account_balance": s["balance"], "risk_percent": self.risk_percent,
                "point_value": 20.0, "daily_pnl": s["daily_pnl"], "total_drawdown": s["drawdown"]}

    def advance(self, candle):
        if self.index >= len(self.rows):
            raise ValueError("historical segment exhausted")
        row = self.rows[self.index]
        if candle != BacktestSessionV2._normalize_candle(row.candle()):
            raise ValueError("candle differs from certified single-contract segment")
        self.current = row
        self.index += 1
        self.account.ensure_trading_day()
        if self.account.get_state()["trading_day"] != row.trading_date:
            raise ValueError("historical trading date mismatch")

    def capture_state(self):
        s = self.account.get_state()
        fields = ("balance", "equity", "peak_equity", "realized_pnl", "daily_pnl", "drawdown",
                  "trading_day", "open_positions", "trading_blocked")
        self.states.append({"index": self.index, **{k: s[k] for k in fields}})

    def record_close(self, position):
        identifier = position["position_id"]
        if any(t["position_id"] == identifier for t in self.completed):
            raise RuntimeError("duplicate canonical realization")
        state = self.account.get_state()
        journal = next(t for t in self.journal.trades if t.position_id == identifier)
        if journal.status != "CLOSED" or journal.pnl != position["realized_pnl"]:
            raise RuntimeError("journal/accounting synchronization failed")
        record = {**self.entries[identifier], "position_id": identifier, "contract": self.contract,
                  "strategy_version": self.strategy_version, "config_hash": self.config_hash,
                  "source_sha256": self.current.source_sha256, "exit_source_row": self.current.source_row,
                  "exit_index": self.index, "exit_time": self.current.available_at.isoformat(),
                  "trading_date": self.current.trading_date, "direction": position["direction"],
                  "quantity": position["quantity"], "executed_entry": position["entry_price"],
                  "stop": position["stop_loss"], "target": position["take_profit"],
                  "exit_trigger": position["close_reason"], "trigger_price": position["trigger_price"],
                  "executed_exit": position["exit_price"], "point_value": position["point_value"],
                  "gross_pnl": position["gross_pnl"], "fees": position["execution_fees"],
                  "net_pnl": position["realized_pnl"], "balance_after": state["balance"],
                  "daily_pnl_after": state["daily_pnl"], "drawdown_after": state["drawdown"],
                  "reason_codes": [position["close_reason"], "CANONICAL_HISTORICAL_REALIZATION"]}
        journal.historical = record
        self.completed.append(record)
        if round(sum(t["net_pnl"] for t in self.completed), 10) != state["realized_pnl"]:
            raise RuntimeError("duplicate or missing account realization")

    def run(self):
        return self.engine.run_single_pass(tuple(r.candle() for r in self.rows))
