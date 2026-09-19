from dataclasses import asdict, replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.backtesting.backtest_engine import BacktestEngine
from backend.backtesting.backtest_engine_pipeline_adapter_v2 import BacktestEnginePipelineAdapterV2
from backend.backtesting.backtest_execution_adapter_v2 import BacktestExecutionAdapterV2
from backend.backtesting.backtest_runner_v2 import BacktestRunnerV2
from backend.backtesting.backtest_session_v2 import BacktestSessionV2, _CandleView
from backend.backtesting.backtest_trade_plan_adapter_v2 import BacktestTradePlanAdapterV2
from backend.backtesting.replay_engine_v2 import ReplayEngineV2
from backend.backtesting.replay_market_data_bridge_v2 import ReplayMarketDataBridgeV2
from backend.models.candle import Candle
from backend.services.signal_submission_target_v2 import SignalSubmissionTargetV2
from backend.signals.signal_generator_v2 import SignalGeneratorV2
from backend.strategies.trading_strategy_v2 import TradingActionV2, TradingDecisionV2
from backend.tests.test_production_certified_outcome_v17 import api_settings


@pytest.fixture(autouse=True)
def canonical_test_account(api_settings):
    # Existing canonical profile, isolated from local account selection.
    return api_settings


def candles(count):
    return [
        Candle("NQ", "1m", 20000.0 + i, 20000.5 + i, 19999.5 + i,
               20000.0 + i, 1000, datetime(2026, 1, 1) + timedelta(minutes=i))
        for i in range(count)
    ]


class Strategy:
    def __init__(self, actions=()):
        self.actions = iter(actions)
        self.contexts = []

    def run(self, context):
        self.contexts.append(context)
        action = next(self.actions, TradingActionV2.HOLD)
        price = context["candle"]["close"]
        return TradingDecisionV2(
            action=action, confidence=0.95, reason="synthetic session contract",
            metadata={"stop_loss": price - 30, "take_profit": price + 60,
                      "contracts": 1, "confluence_score": 0.9, "grade": "A+"},
        )


class Target(SignalSubmissionTargetV2):
    def __init__(self, results, close_at=None):
        self.results = iter(results)
        self.calls = []
        self.updates = []
        self.close_at = close_at

    def submit_signal(self, **kwargs):
        self.calls.append(kwargs)
        return next(self.results)

    def update_position(self, *, position_id, current_price):
        self.updates.append((position_id, current_price))
        closed = self.close_at is not None and current_price >= self.close_at
        return {"position": {"status": "CLOSED" if closed else "OPEN"}}


def build(*, actions=(), target=None, minimum=1, window=50, signals=True):
    replay = ReplayEngineV2()
    replay.load = Mock(wraps=replay.load)
    bridge = ReplayMarketDataBridgeV2()
    bridge.publish = Mock(wraps=bridge.publish)
    runner = BacktestRunnerV2(replay_engine_v2=replay, replay_market_data_bridge_v2=bridge)
    runner.run = Mock(wraps=runner.run)
    strategy = Strategy(actions)
    executor = BacktestExecutionAdapterV2()
    executor.execute = Mock(wraps=executor.execute)
    executor.simulator.simulate = Mock(wraps=executor.simulator.simulate)
    session = BacktestSessionV2(
        backtest_runner_v2=runner, strategy_runner_v2=strategy,
        trade_executor_v2=executor,
        backtest_trade_plan_adapter_v2=BacktestTradePlanAdapterV2() if signals else None,
        signal_generator_v2=SignalGeneratorV2(
            minimum_probability=0.8, minimum_confluence_score=0.8,
            allowed_grades={"A+", "A"},
        ) if signals else None,
        signal_submission_target_v2=target, analysis_window=window,
    )
    engine = BacktestEngine(
        pipeline=BacktestEnginePipelineAdapterV2(pipeline=SimpleNamespace(backtest_session_v2=session)),
        minimum_candles=minimum,
    )
    return engine, session, strategy, executor


def test_chronological_once_bounded_history_warmup_and_final_candle():
    class NoSliceList(list):
        def __getitem__(self, index):
            assert not isinstance(index, slice), "Input prefix/suffix copied"
            return super().__getitem__(index)

    data = NoSliceList(candles(100))
    target = Target([])
    engine, session, strategy, executor = build(minimum=5, target=target)
    result = engine.run_single_pass(data)
    assert [c["signal_index"] for c in strategy.contexts] == list(range(5, 100))
    for context in strategy.contexts:
        index = context["signal_index"]
        assert len(context["history"]) == min(index, 50)
        assert context["history"][-1] is context["candle"]
        assert [c["timestamp"] for c in context["history"]] == [
            data[i].timestamp for i in range(max(0, index - 50), index)
        ]
        assert "future_candles" not in context
    assert len(session.candle_history) == 100
    runner = session.backtest_runner_v2
    runner.run.assert_called_once()
    runner.replay_engine_v2.load.assert_called_once()
    assert runner.replay_market_data_bridge_v2.publish.call_count == 100
    assert result.total_candles == 100
    assert result.total_signals == 0
    assert result.trades == []
    executor.execute.assert_not_called()
    assert target.calls == []


@pytest.mark.parametrize("count,minimum,indices", [(1, 1, []), (3, 5, []), (5, 5, []), (6, 5, [5])])
def test_warmup_edges(count, minimum, indices):
    engine, session, strategy, executor = build(minimum=minimum)
    engine.run_single_pass(candles(count))
    assert [c["signal_index"] for c in strategy.contexts] == indices
    assert len(session.candle_history) == count
    executor.execute.assert_not_called()


def test_future_perturbation_does_not_change_earlier_decisions_or_context():
    data = candles(8)
    changed = [replace(c) for c in data]
    for i in range(4, len(changed)):
        changed[i] = replace(changed[i], high=30000, low=10000, close=25000)
    runs = []
    for sample in (data, changed):
        engine, session, strategy, executor = build(actions=[TradingActionV2.BUY])
        result = engine.run_single_pass(sample)
        runs.append((session.decisions, strategy.contexts, result))
    assert runs[0][0][:4] == runs[1][0][:4]
    assert runs[0][1][:4] == runs[1][1][:4]
    # Future OHLC can change the outcome; it cannot change the prior decision.
    assert runs[0][2].trades[0].pnl != runs[1][2].trades[0].pnl


@pytest.mark.parametrize("response", [{"accepted": False}, {}, {"accepted": None}, {"accepted": "true"}, {"accepted": 1}, None])
def test_unaccepted_submission_has_zero_execution(response):
    target = Target([response])
    engine, session, strategy, executor = build(actions=[TradingActionV2.BUY], target=target)
    result = engine.run_single_pass(candles(3))
    assert len(target.calls) == 1
    assert session.submission_results == [response]
    executor.execute.assert_not_called()
    executor.simulator.simulate.assert_not_called()
    assert session.simulated_trades == result.trades == []
    assert result.statistics.total_trades == 0
    assert result.equity_curve.balance == 17000


def test_accepted_rejected_and_exact_once_accounting_with_stop_precedence():
    data = candles(4)
    data[1] = replace(data[1], high=20100, low=19960)
    data[3] = replace(data[3], high=20100, low=20002)
    target = Target([{"accepted": True}, {"accepted": False}, {"accepted": True}])
    engine, session, strategy, executor = build(actions=[TradingActionV2.BUY] * 3, target=target)
    result = engine.run_single_pass(data)
    assert result.total_signals == result.authorized_trades == 3
    assert result.blocked_signals == 0
    assert len(target.calls) == 3
    assert executor.execute.call_count == executor.simulator.simulate.call_count == 2
    assert [t.pnl for t in result.trades] == [-600.0, 1200.0]
    assert result.trades[0].reasoning[0] == "STOP_LOSS"
    assert result.statistics.total_trades == result.metrics["total_trades"] == 2
    assert result.statistics.net_profit == result.metrics["net_profit"] == 600
    assert result.statistics.max_drawdown == result.equity_curve.max_drawdown == 600
    assert [p.balance for p in result.equity_curve.points] == [16400, 17600]
    assert result.equity_curve.balance == 17600


def test_standalone_executor_without_signal_pipeline():
    engine, session, strategy, executor = build(actions=[TradingActionV2.BUY], signals=False)
    result = engine.run_single_pass(candles(3))
    executor.execute.assert_called_once()
    assert result.total_signals == 0
    assert len(result.trades) == result.statistics.total_trades == 1


def test_risk_veto_survives_acceptance():
    engine, session, strategy, executor = build(actions=[TradingActionV2.BUY], target=Target([{"accepted": True}]))
    session.risk_pipeline.evaluate = Mock(return_value=SimpleNamespace(allowed=False))
    result = engine.run_single_pass(candles(3))
    session.risk_pipeline.evaluate.assert_called_once()
    executor.execute.assert_not_called()
    assert result.trades == []


def test_position_persists_and_final_candle_updates_without_new_entry():
    target = Target([{"accepted": True, "active_position_id": "position-1"}], close_at=20003)
    engine, session, strategy, executor = build(
        actions=[TradingActionV2.BUY, TradingActionV2.HOLD, TradingActionV2.BUY],
        target=target, minimum=2,
    )
    engine.run_single_pass(candles(4))
    assert [c["has_active_position"] for c in strategy.contexts] == [False, True]
    assert target.updates == [("position-1", 20002), ("position-1", 20003)]
    assert session.active_position_id is None
    assert len(target.calls) == 1
    executor.execute.assert_called_once()


def test_entry_candle_excluded_and_view_matches_existing_simulator():
    data = candles(5)
    data[0] = replace(data[0], high=30000, low=10000)
    engine, session, strategy, executor = build(actions=[TradingActionV2.BUY])
    result = engine.run_single_pass(data)
    view = executor.simulator.simulate.call_args.kwargs["candles"]
    assert isinstance(view, _CandleView)
    assert list(view) == data[1:]
    assert view[0] is data[1] and view[-1] is data[-1]
    assert list(view[::-1]) == data[:0:-1]
    kwargs = dict(executor.simulator.simulate.call_args.kwargs)
    kwargs["candles"] = data[1:]
    reference = executor.simulator.simulate(**kwargs)
    assert asdict(result.trades[0]) == asdict(reference)
    assert result.trades[0].reasoning[0] == "END_OF_DATA"


def test_equivalence_with_direct_sequential_session_for_common_decisions():
    data = candles(6)
    optimized, session, strategy, executor = build(
        actions=[TradingActionV2.BUY], target=Target([{"accepted": True}]),
    )
    result = optimized.run_single_pass(data)
    _, reference, reference_strategy, _ = build(
        actions=[TradingActionV2.BUY], target=Target([{"accepted": True}]),
    )
    reference.backtest_runner_v2.replay_engine_v2.load(data)
    # The sole entry is at candle zero, so this legacy session's fixed suffix
    # is an equivalent execution input. Exclude its final HOLD comparison.
    reference.future_candles = data[1:]
    reference.run()
    assert session.decisions == reference.decisions[:-1]
    # V29R intentionally replaces only the single-pass HTF aliases and adds
    # an explicit completion clock. Base/execution context remains equivalent.
    common = lambda c: {k: v for k, v in c.items()
                        if k not in {"history_15m", "history_1h", "decision_time"}}
    assert [common(c) for c in strategy.contexts] == [common(c) for c in reference_strategy.contexts[:-1]]
    assert all(c["history_15m"] == c["history_1h"] == [] for c in strategy.contexts)
    assert session.trade_plans == reference.trade_plans
    assert [asdict(t) for t in result.trades] == [asdict(t) for t in reference.simulated_trades]
    assert session.submission_results == reference.submission_results


def test_blocked_plan_accounting_remains_separate_from_submission_acceptance():
    target = Target([{"accepted": False}])
    engine, session, strategy, executor = build(actions=[TradingActionV2.BUY], target=target)
    build_plan = session.backtest_trade_plan_adapter_v2.build_trade_plan
    session.backtest_trade_plan_adapter_v2.build_trade_plan = lambda **kw: replace(
        build_plan(**kw), authorized=False,
    )
    result = engine.run_single_pass(candles(3))
    assert result.total_signals == result.blocked_signals == 1
    assert result.authorized_trades == 0
    assert result.trades == []
    executor.execute.assert_not_called()


def test_fresh_composition_required_and_input_validation_before_execution():
    engine, session, strategy, executor = build()
    data = candles(3)
    with pytest.raises(ValueError, match="chronological"):
        engine.run_single_pass(list(reversed(data)))
    with pytest.raises(ValueError, match="chronological"):
        engine.run_single_pass([data[0], data[0]])
    with pytest.raises(ValueError, match="requires candles"):
        engine.run_single_pass([])
    with pytest.raises(TypeError, match="Candle"):
        engine.run_single_pass([{}])
    assert strategy.contexts == []
    engine.run_single_pass(data)
    with pytest.raises(RuntimeError, match="fresh session"):
        engine.run_single_pass(data)
    session.backtest_runner_v2.replay_engine_v2.load.assert_called_once()
    with pytest.raises(TypeError, match="BacktestEnginePipelineAdapterV2"):
        BacktestEngine(pipeline=SimpleNamespace()).run_single_pass(data)


def test_real_production_strategy_and_lifecycle_on_deterministic_fixture(tmp_path, api_settings):
    from backend.backtesting.csv_candle_loader_v2 import CsvCandleLoaderV2
    from backend.backtesting.parameter_backtest_engine_factory_v2 import ParameterBacktestEngineFactoryV2
    from backend.tests.test_production_certified_outcome_v17 import _write_relative_volatility_ten_trade_csv

    path = tmp_path / "synthetic.csv"
    _write_relative_volatility_ten_trade_csv(path, opportunities=2)
    data = CsvCandleLoaderV2(csv_path=path, symbol="NQ", timeframe="1m").load()
    engine = ParameterBacktestEngineFactoryV2(csv_path=None, settings=api_settings)(
        {"ema": 5, "stop_loss": 30, "take_profit": 60},
    )
    session = engine.pipeline.pipeline.backtest_session_v2
    strategy = session.strategy_runner_v2
    strategy.run = Mock(wraps=strategy.run)
    result = engine.run_single_pass(data)
    indices = [c.args[0]["signal_index"] for c in strategy.run.call_args_list]
    assert indices == list(range(5, len(data)))
    assert all(len(c.args[0]["history"]) <= 50 for c in strategy.run.call_args_list)
    accepted = [s for s in session.submission_results if isinstance(s, dict) and s.get("accepted") is True]
    # This 350-minute fixture cannot meet the structure consumer's ten
    # completed hourly bars. The old trades depended on falsely aliased HTFs.
    assert all(len(c.args[0]["history_1h"]) < 10 for c in strategy.run.call_args_list)
    assert all(d.action is TradingActionV2.HOLD for d in session.decisions)
    assert session.signals == session.submission_results == accepted == []
    assert len(result.trades) == len(accepted)
    assert result.statistics.total_trades == len(result.equity_curve.points) == len(accepted)
