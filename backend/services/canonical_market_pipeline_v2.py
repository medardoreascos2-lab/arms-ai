"""Application orchestration over the existing candle and intelligence owners.

This boundary evaluates candidates only. Submission is a separate authorized
command to TradeLifecycleServiceV2, which rechecks every runtime safety gate.
"""
from dataclasses import asdict
import hashlib
import json

from backend.instruments.instrument_profile_engine import InstrumentProfileEngine
from backend.services.live_market_analysis_service import LiveMarketAnalysisService


class CanonicalMarketPipelineV2:
    def __init__(self, state):
        self.state = state
        self.store = state.live_candle_store
        self.lifecycle = state.trade_lifecycle_service_v2
        runtime = state.runtime_context_v2
        if runtime is None or runtime.trade_lifecycle_service is not self.lifecycle:
            raise ValueError("canonical market runtime unavailable")
        if state.position_manager is not runtime.position_manager:
            raise ValueError("canonical position ownership mismatch")

    def ingest(self, candle):
        with self.store.ingestion_lock:
            inserted = self.store.ingest(candle)
            count = self.store.count(symbol=candle.symbol, timeframe=candle.timeframe)
            result = {"status": "stored" if inserted else "duplicate",
                      "symbol": candle.symbol, "timeframe": candle.timeframe,
                      "timestamp": candle.timestamp.isoformat(), "count": count,
                      "analysis_generated": False}
            if not inserted:
                return result
            result["trend"] = self.state.trend_engine_v2.analyze(
                symbol=candle.symbol, timeframe=candle.timeframe)
            # OHLC history is not a current executable quote or price-monitor
            # command. Price observations retain their dedicated canonical API.
            if count >= LiveMarketAnalysisService.MINIMUM_CANDLES:
                result["analysis"] = self.analyze(
                    symbol=candle.symbol, timeframe=candle.timeframe, candle_limit=50)
                result["analysis_generated"] = True
            return result

    def analyze(self, *, symbol, timeframe, candle_limit):
        symbol, timeframe = symbol.strip().upper(), timeframe.strip().lower()
        with self.store.ingestion_lock:
            state = self.state
            profile = state.account_config_manager_v2.get_active_account()
            balance = self.lifecycle.portfolio_manager_v2.get_available_balance()
            point_value = InstrumentProfileEngine().get_profile(symbol=symbol)["point_value"]
            admission = self.lifecycle.runtime_admission_v2
            # Resolve refreshed authorities at evaluation time, not cached copies.
            owners = {name: getattr(state, name) for name in (
                "smart_money_engine_v2", "market_regime_engine", "confluence_engine_v2",
                "probability_engine_v2", "execution_decision_engine_v2", "decision_council_v2",
                "multi_timeframe_decision_engine_v2", "market_context_engine_v2",
                "trade_planner_v2", "trade_validator_v2", "signal_generator_v2")}
            service = LiveMarketAnalysisService(
                candle_store=self.store, analysis_store=state.live_analysis_store,
                signal_store=state.live_signal_store, signal_history_store=state.signal_history_store,
                execution_manager=state.signal_execution_manager,
                account_risk_guard=state.account_risk_guard,
                trade_history_store=state.trade_history_store,
                position_sizing_engine=state.position_sizing_engine,
                execution_decision_engine=state.execution_decision_engine,
                trade_lifecycle_service_v2=self.lifecycle,
                market_hours_service_v2=admission.market_hours_provider.get_market_hours_service(),
                economic_news_authority_v2=admission.news_provider.get_economic_news_authority(),
                runtime_spread_authority_v2=admission.runtime_spread_authority,
                candidate_only=True, **owners)
            result = service.analyze(symbol=symbol, timeframe=timeframe,
                candle_limit=candle_limit, account_balance=balance,
                risk_percent=profile.risk_percent, point_value=point_value,
                reward_risk_ratio=admission.settings.minimum_reward_risk_ratio)
            candles = self.store.get_latest(symbol=symbol, timeframe=timeframe, limit=candle_limit)
            source_hash = hashlib.sha256(json.dumps([asdict(c) for c in candles],
                sort_keys=True, default=str).encode()).hexdigest()
            safety = state.account_switch_safety_v2
            identity = {"account_id": safety.identity.account_id,
                        "profile_name": safety.identity.profile_name,
                        "runtime_generation": state.account_runtime_generation}
            candidate = result["signal_v2"]
            candidate.update(identity)
            candidate.update(generated_at=candles[-1].timestamp.isoformat(),
                             source="LIVE_MARKET_ANALYSIS", source_hash=source_hash)
            candidate["submission_id"] = hashlib.sha256(json.dumps(
                {**identity, "source_hash": source_hash}, sort_keys=True).encode()).hexdigest()
            account = self.lifecycle.portfolio_manager_v2.account_state_manager_v2.get_state()
            result["admission_request"] = {
                "signal": dict(candidate), "order_type": "MARKET",
                "risk_context": {**identity, "account_balance": balance,
                    "risk_percent": profile.risk_percent, "point_value": point_value,
                    "daily_pnl": account["daily_pnl"], "total_drawdown": account["drawdown"]},
            }
            result["candidate_only"] = True
            state.live_analysis_store.save(result)
            return result
