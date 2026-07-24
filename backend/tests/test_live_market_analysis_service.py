from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.models.candle import Candle
from backend.services.live_analysis_store import (
    LiveAnalysisStore,
)
from backend.services.live_candle_store import (
    LiveCandleStore,
)
from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)


def populate_store(
    store: LiveCandleStore,
    total: int = 60,
) -> None:
    start = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone.utc,
    )

    for index in range(total):
        base = 21600.0 + index * 1.5

        store.add(
            Candle(
                symbol="NQ",
                timeframe="5m",
                open=base,
                high=base + 4.0,
                low=base - 2.0,
                close=base + 2.5,
                volume=1000.0 + index * 10,
                timestamp=(
                    start
                    + timedelta(
                        minutes=index * 5
                    )
                ),
            )
        )


def test_analyzes_and_saves_latest_result():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert result["symbol"] == "NQ"
    assert result["timeframe"] == "5m"
    assert result["current_price"] == 21691.0
    assert "analyzed_at" in result

    saved = analysis_store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert saved is not None
    assert saved["current_price"] == 21691.0
    assert saved["analyzed_at"] == result["analyzed_at"]


def test_uses_latest_requested_candles():
    candle_store = LiveCandleStore(
        max_candles=100
    )

    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store,
        total=80,
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert result["current_price"] == 21721.0


def test_rejects_insufficient_candles():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store,
        total=20,
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    with pytest.raises(
        ValueError,
        match="velas",
    ):
        service.analyze(
            symbol="NQ",
            timeframe="5m",
            candle_limit=60,
            account_balance=17000.0,
            risk_percent=0.5,
            point_value=2.0,
            reward_risk_ratio=2.0,
        )


def test_can_analyze_when_minimum_is_reached():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store,
        total=50,
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    assert service.can_analyze(
        symbol="NQ",
        timeframe="5m",
        minimum_candles=50,
    ) is True


def test_cannot_analyze_before_minimum():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store,
        total=49,
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    assert service.can_analyze(
        symbol="NQ",
        timeframe="5m",
        minimum_candles=50,
    ) is False


def test_generates_signal_with_analysis():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "signal" in result

    signal = result["signal"]

    assert signal["symbol"] == "NQ"
    assert signal["timeframe"] == "5m"
    assert signal["action"] in {
        "BUY",
        "SELL",
        "WAIT",
    }
    assert "approved" in signal
    assert "score" in signal
    assert "grade" in signal
    assert "probability" in signal
    assert "entry_price" in signal
    assert "stop_loss" in signal
    assert "take_profit" in signal


def test_saved_analysis_contains_signal():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    saved = analysis_store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert saved is not None
    assert "signal" in saved
    assert saved["signal"]["action"] in {
        "BUY",
        "SELL",
        "WAIT",
    }


def test_saves_generated_signal_in_live_signal_store():
    from backend.services.live_signal_store import (
        LiveSignalStore,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()
    signal_store = LiveSignalStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        signal_store=signal_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    saved_signal = signal_store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert saved_signal is not None
    assert saved_signal == result["signal"]
    assert saved_signal["action"] in {
        "BUY",
        "SELL",
        "WAIT",
    }


def test_appends_generated_signal_to_history():
    from backend.services.live_signal_store import (
        LiveSignalStore,
    )
    from backend.services.signal_history_store import (
        SignalHistoryStore,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()
    signal_store = LiveSignalStore()
    history_store = SignalHistoryStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        signal_store=signal_store,
        signal_history_store=history_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    history = history_store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(history) == 1
    assert history[0] == result["signal"]
    assert "generated_at" in history[0]


def test_evaluates_generated_signal_for_execution():
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    execution_manager = SignalExecutionManager(
        cooldown_minutes=15
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=execution_manager,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "execution" in result

    execution = result["execution"]

    assert execution["action"] in {
        "BUY",
        "SELL",
        "WAIT",
    }
    assert "accepted" in execution
    assert "status" in execution


def test_rejects_duplicate_signal_inside_cooldown():
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    execution_manager = SignalExecutionManager(
        cooldown_minutes=15
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=execution_manager,
    )

    first = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    second = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if first["signal"]["action"] in {
        "BUY",
        "SELL",
    }:
        assert first["execution"]["accepted"] is True
        assert second["execution"]["accepted"] is False
        assert second["execution"]["status"] == "DUPLICATE"
    else:
        assert first["execution"]["accepted"] is False
        assert second["execution"]["accepted"] is False


def test_saves_only_accepted_execution():
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.services.executable_signal_store import (
        ExecutableSignalStore,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()
    executable_store = ExecutableSignalStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        executable_signal_store=(
            executable_store
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    saved = executable_store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    if result["execution"]["accepted"]:
        assert saved is not None
        assert saved == result["execution"]
    else:
        assert saved is None


def test_does_not_replace_executable_signal_with_duplicate():
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.services.executable_signal_store import (
        ExecutableSignalStore,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()
    executable_store = ExecutableSignalStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        executable_signal_store=(
            executable_store
        ),
    )

    first = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    saved_before = executable_store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    second = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    saved_after = executable_store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    if (
        first["execution"]["accepted"]
        and second["execution"]["status"]
        == "DUPLICATE"
    ):
        assert saved_before is not None
        assert saved_after == saved_before


def test_executes_accepted_signal_in_simulated_mode():
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.execution.trade_execution_engine import (
        TradeExecutionEngine,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        trade_execution_engine=TradeExecutionEngine(
            mode="SIMULATED"
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if result["execution"]["accepted"]:
        assert "trade_execution" in result
        assert (
            result["trade_execution"]["executed"]
            is True
        )
        assert (
            result["trade_execution"]["status"]
            == "SIMULATED"
        )
        assert (
            result["trade_execution"]["mode"]
            == "SIMULATED"
        )
    else:
        assert "trade_execution" not in result


def test_does_not_execute_duplicate_signal():
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.execution.trade_execution_engine import (
        TradeExecutionEngine,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        trade_execution_engine=TradeExecutionEngine(
            mode="SIMULATED"
        ),
    )

    first = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    second = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if (
        first["execution"]["accepted"]
        and second["execution"]["status"]
        == "DUPLICATE"
    ):
        assert "trade_execution" in first
        assert "trade_execution" not in second


def test_opens_position_after_simulated_execution():
    from backend.execution.position_manager import (
        PositionManager,
    )
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.execution.trade_execution_engine import (
        TradeExecutionEngine,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()
    position_manager = PositionManager()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        trade_execution_engine=TradeExecutionEngine(
            mode="SIMULATED"
        ),
        position_manager=position_manager,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if "trade_execution" in result:
        assert "position" in result

        position = position_manager.get_open_position(
            symbol="NQ",
            timeframe="5m",
        )

        assert position is not None
        assert position == result["position"]
        assert position["status"] == "OPEN"
    else:
        assert (
            position_manager.get_open_position(
                symbol="NQ",
                timeframe="5m",
            )
            is None
        )


def test_does_not_open_second_position_same_market():
    from backend.execution.position_manager import (
        PositionManager,
    )
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.execution.trade_execution_engine import (
        TradeExecutionEngine,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()
    position_manager = PositionManager()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=0
        ),
        trade_execution_engine=TradeExecutionEngine(
            mode="SIMULATED"
        ),
        position_manager=position_manager,
    )

    first = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if "trade_execution" not in first:
        return

    second = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "position_error" in second
    assert "posición abierta" in second["position_error"]


def test_blocks_trade_when_account_risk_guard_rejects():
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.execution.trade_execution_engine import (
        TradeExecutionEngine,
    )
    from backend.account_risk.account_risk_guard import (
        AccountRiskGuard,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    risk_guard = AccountRiskGuard(
        daily_loss_limit=3000.0,
        max_trades_per_day=4,
        max_consecutive_losses=3,
        max_open_positions=1,
        max_risk_per_trade=50.0,
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        trade_execution_engine=TradeExecutionEngine(
            mode="SIMULATED"
        ),
        account_risk_guard=risk_guard,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if result["execution"]["accepted"]:
        assert "account_risk" in result
        assert (
            result["account_risk"]["approved"]
            is False
        )
        assert (
            "max_risk_per_trade"
            in result["account_risk"]["reasons"]
        )
        assert "trade_execution" not in result


def test_executes_trade_when_account_risk_guard_approves():
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.execution.trade_execution_engine import (
        TradeExecutionEngine,
    )
    from backend.account_risk.account_risk_guard import (
        AccountRiskGuard,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    risk_guard = AccountRiskGuard(
        daily_loss_limit=3000.0,
        max_trades_per_day=4,
        max_consecutive_losses=3,
        max_open_positions=1,
        max_risk_per_trade=250.0,
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        trade_execution_engine=TradeExecutionEngine(
            mode="SIMULATED"
        ),
        account_risk_guard=risk_guard,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if result["execution"]["accepted"]:
        assert "account_risk" in result
        assert (
            result["account_risk"]["approved"]
            is True
        )
        assert "trade_execution" in result


def test_account_risk_guard_uses_trade_history():
    from datetime import (
        datetime,
        timezone,
    )

    from backend.account_risk.account_risk_guard import (
        AccountRiskGuard,
    )
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.execution.trade_execution_engine import (
        TradeExecutionEngine,
    )
    from backend.services.trade_history_store import (
        TradeHistoryStore,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()
    trade_history_store = TradeHistoryStore()

    populate_store(
        candle_store
    )

    trade_history_store.append(
        {
            "symbol": "NQ",
            "timeframe": "5m",
            "side": "LONG",
            "status": "CLOSED",
            "closed": True,
            "entry_price": 21600.0,
            "exit_price": 21500.0,
            "stop_loss": 21500.0,
            "take_profit": 21800.0,
            "contracts": 1,
            "opened_at": datetime(
                2026,
                7,
                22,
                9,
                0,
                tzinfo=timezone.utc,
            ),
            "closed_at": datetime(
                2026,
                7,
                22,
                9,
                30,
                tzinfo=timezone.utc,
            ),
            "close_reason": "STOP_LOSS",
            "pnl_points": -100.0,
            "pnl": -3000.0,
        }
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        trade_execution_engine=TradeExecutionEngine(
            mode="SIMULATED"
        ),
        account_risk_guard=AccountRiskGuard(
            daily_loss_limit=3000.0,
            max_trades_per_day=4,
            max_consecutive_losses=3,
            max_open_positions=1,
            max_risk_per_trade=250.0,
        ),
        trade_history_store=trade_history_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if result["execution"]["accepted"]:
        assert result["account_risk"]["approved"] is False
        assert (
            "daily_loss_limit"
            in result["account_risk"]["reasons"]
        )
        assert result["account_risk"]["trade_count"] == 1
        assert "trade_execution" not in result


def test_calculates_position_size_for_accepted_signal():
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.risk_management.position_sizing_engine import (
        PositionSizingEngine,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        position_sizing_engine=PositionSizingEngine(
            minimum_contracts=1,
            maximum_contracts=20,
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if result["execution"]["accepted"]:
        assert "position_sizing" in result
        assert (
            result["position_sizing"]["approved"]
            is True
        )
        assert (
            result["position_sizing"]["contracts"]
            >= 1
        )
        assert (
            result["execution"]["contracts"]
            == result["position_sizing"]["contracts"]
        )


def test_blocks_execution_when_position_size_is_not_approved():
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.execution.trade_execution_engine import (
        TradeExecutionEngine,
    )
    from backend.risk_management.position_sizing_engine import (
        PositionSizingEngine,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        trade_execution_engine=TradeExecutionEngine(
            mode="SIMULATED"
        ),
        position_sizing_engine=PositionSizingEngine(
            minimum_contracts=1,
            maximum_contracts=20,
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=100.0,
        risk_percent=0.5,
        point_value=20.0,
        reward_risk_ratio=2.0,
    )

    if result["execution"]["accepted"]:
        assert "position_sizing" in result
        assert (
            result["position_sizing"]["approved"]
            is False
        )
        assert (
            result["position_sizing"]["status"]
            == "INSUFFICIENT_RISK_BUDGET"
        )
        assert "trade_execution" not in result


def test_omits_position_sizing_when_not_configured():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "position_sizing" not in result


def test_uses_instrument_profile_for_position_sizing():
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.instruments.instrument_profile_engine import (
        InstrumentProfileEngine,
    )
    from backend.risk_management.position_sizing_engine import (
        PositionSizingEngine,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        position_sizing_engine=PositionSizingEngine(
            minimum_contracts=1,
            maximum_contracts=20,
            instrument_profile_engine=(
                InstrumentProfileEngine()
            ),
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=150000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if result["execution"]["accepted"]:
        sizing = result["position_sizing"]

        assert sizing["symbol"] == "NQ"
        assert sizing["point_value"] == 20.0
        assert sizing["tick_size"] == 0.25
        assert sizing["tick_value"] == 5.0
        assert sizing["maximum_contracts"] == 5
        assert (
            result["execution"]["contracts"]
            == sizing["contracts"]
        )


def test_falls_back_to_manual_point_value_for_unsupported_symbol():
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.instruments.instrument_profile_engine import (
        InstrumentProfileEngine,
    )
    from backend.risk_management.position_sizing_engine import (
        PositionSizingEngine,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    source_candles = (
        candle_store.get_latest(
            symbol="NQ",
            timeframe="5m",
            limit=60,
        )
    )

    for candle in source_candles:
        if hasattr(
            candle,
            "model_copy",
        ):
            cloned_candle = (
                candle.model_copy(
                    update={
                        "symbol": "UNKNOWN",
                    }
                )
            )
        else:
            from dataclasses import replace

            cloned_candle = replace(
                candle,
                symbol="UNKNOWN",
            )

        candle_store.add(
            cloned_candle
        )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        position_sizing_engine=PositionSizingEngine(
            minimum_contracts=1,
            maximum_contracts=20,
            instrument_profile_engine=(
                InstrumentProfileEngine()
            ),
        ),
    )

    result = service.analyze(
        symbol="UNKNOWN",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if result["execution"]["accepted"]:
        sizing = result["position_sizing"]

        assert "symbol" not in sizing
        assert sizing["risk_per_contract"] > 0


def test_execution_decision_allows_approved_trade():
    from backend.execution.execution_decision_engine import (
        ExecutionDecisionEngine,
    )
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.execution.trade_execution_engine import (
        TradeExecutionEngine,
    )
    from backend.risk_management.position_sizing_engine import (
        PositionSizingEngine,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        trade_execution_engine=TradeExecutionEngine(
            mode="SIMULATED"
        ),
        position_sizing_engine=PositionSizingEngine(
            minimum_contracts=1,
            maximum_contracts=20,
        ),
        execution_decision_engine=(
            ExecutionDecisionEngine(
                minimum_confidence=0.0,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if result["execution"]["accepted"]:
        assert "execution_decision" in result
        assert (
            result["execution_decision"][
                "decision"
            ]
            == "EXECUTE"
        )
        assert (
            result["execution_decision"][
                "approved"
            ]
            is True
        )
        assert "trade_execution" in result


def test_execution_decision_blocks_rejected_sizing():
    from backend.execution.execution_decision_engine import (
        ExecutionDecisionEngine,
    )
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.execution.trade_execution_engine import (
        TradeExecutionEngine,
    )
    from backend.risk_management.position_sizing_engine import (
        PositionSizingEngine,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        trade_execution_engine=TradeExecutionEngine(
            mode="SIMULATED"
        ),
        position_sizing_engine=PositionSizingEngine(
            minimum_contracts=1,
            maximum_contracts=20,
        ),
        execution_decision_engine=(
            ExecutionDecisionEngine(
                minimum_confidence=0.0,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=100.0,
        risk_percent=0.5,
        point_value=20.0,
        reward_risk_ratio=2.0,
    )

    if result["execution"]["accepted"]:
        assert (
            result["position_sizing"][
                "approved"
            ]
            is False
        )
        assert (
            result["execution_decision"][
                "decision"
            ]
            == "BLOCK"
        )
        assert (
            "position_sizing_rejected"
            in result["execution_decision"][
                "reasons"
            ]
        )
        assert "trade_execution" not in result


def test_execution_decision_waits_for_low_confidence():
    from backend.execution.execution_decision_engine import (
        ExecutionDecisionEngine,
    )
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.execution.trade_execution_engine import (
        TradeExecutionEngine,
    )
    from backend.risk_management.position_sizing_engine import (
        PositionSizingEngine,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        trade_execution_engine=TradeExecutionEngine(
            mode="SIMULATED"
        ),
        position_sizing_engine=PositionSizingEngine(
            minimum_contracts=1,
            maximum_contracts=20,
        ),
        execution_decision_engine=(
            ExecutionDecisionEngine(
                minimum_confidence=1.0,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if result["execution"]["accepted"]:
        confidence = float(
            result["execution"].get(
                "confidence",
                0.0,
            )
        )

        if confidence < 1.0:
            assert (
                result["execution_decision"][
                    "decision"
                ]
                == "WAIT"
            )
            assert "trade_execution" not in result


def test_omits_execution_decision_when_not_configured():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "execution_decision" not in result


def test_includes_market_regime_in_execution_decision():
    from backend.execution.execution_decision_engine import (
        ExecutionDecisionEngine,
    )
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.market_analysis.market_regime_engine import (
        MarketRegimeEngine,
    )
    from backend.risk_management.position_sizing_engine import (
        PositionSizingEngine,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        position_sizing_engine=PositionSizingEngine(
            minimum_contracts=1,
            maximum_contracts=20,
        ),
        execution_decision_engine=(
            ExecutionDecisionEngine(
                minimum_confidence=0.0,
            )
        ),
        market_regime_engine=MarketRegimeEngine(
            trend_threshold=0.60,
            high_volatility_threshold=0.80,
            low_volatility_threshold=0.20,
            compression_threshold=0.15,
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "market_regime" in result

    if result["execution"]["accepted"]:
        assert "execution_decision" in result
        assert (
            result["execution_decision"][
                "market_regime"
            ]
            == result["market_regime"][
                "regime"
            ]
        )
        assert (
            result["execution_decision"][
                "market_tradable"
            ]
            == result["market_regime"][
                "tradable"
            ]
        )


def test_market_regime_blocks_non_tradable_market():
    from backend.execution.execution_decision_engine import (
        ExecutionDecisionEngine,
    )
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.execution.trade_execution_engine import (
        TradeExecutionEngine,
    )
    from backend.market_analysis.market_regime_engine import (
        MarketRegimeEngine,
    )
    from backend.risk_management.position_sizing_engine import (
        PositionSizingEngine,
    )

    class AlwaysNoTradeMarketRegimeEngine(
        MarketRegimeEngine
    ):
        def evaluate(
            self,
            *,
            directional_strength: float,
            volatility_score: float,
            compression_score: float,
        ) -> dict[str, object]:
            return {
                "regime": "NO_TRADE",
                "tradable": False,
                "direction": "NEUTRAL",
                "confidence": 1.0,
                "risk_multiplier": 0.0,
            }

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        trade_execution_engine=TradeExecutionEngine(
            mode="SIMULATED"
        ),
        position_sizing_engine=PositionSizingEngine(
            minimum_contracts=1,
            maximum_contracts=20,
        ),
        execution_decision_engine=(
            ExecutionDecisionEngine(
                minimum_confidence=0.0,
            )
        ),
        market_regime_engine=(
            AlwaysNoTradeMarketRegimeEngine(
                trend_threshold=0.60,
                high_volatility_threshold=0.80,
                low_volatility_threshold=0.20,
                compression_threshold=0.15,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert result["market_regime"]["tradable"] is False

    if result["execution"]["accepted"]:
        assert (
            result["execution_decision"][
                "decision"
            ]
            == "BLOCK"
        )
        assert (
            "market_not_tradable"
            in result["execution_decision"][
                "reasons"
            ]
        )
        assert "trade_execution" not in result


def test_omits_market_regime_when_not_configured():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "market_regime" not in result


def test_includes_confluence_v2_result():
    from backend.execution.execution_decision_engine import (
        ExecutionDecisionEngine,
    )
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.market_analysis.market_regime_engine import (
        MarketRegimeEngine,
    )
    from backend.risk_management.position_sizing_engine import (
        PositionSizingEngine,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        position_sizing_engine=PositionSizingEngine(
            minimum_contracts=1,
            maximum_contracts=20,
        ),
        execution_decision_engine=(
            ExecutionDecisionEngine(
                minimum_confidence=0.0,
            )
        ),
        market_regime_engine=MarketRegimeEngine(
            trend_threshold=0.60,
            high_volatility_threshold=0.80,
            low_volatility_threshold=0.20,
            compression_threshold=0.15,
        ),
        confluence_engine_v2=ConfluenceEngineV2(),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "confluence_v2" in result
    assert 0.0 <= result["confluence_v2"]["score"] <= 100.0
    assert result["confluence_v2"]["grade"] in {
        "A+",
        "A",
        "B",
        "C",
    }


def test_confluence_v2_blocks_execution_when_risk_rejects():
    from backend.account_risk.account_risk_guard import (
        AccountRiskGuard,
    )
    from backend.execution.execution_decision_engine import (
        ExecutionDecisionEngine,
    )
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.execution.trade_execution_engine import (
        TradeExecutionEngine,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.risk_management.position_sizing_engine import (
        PositionSizingEngine,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        trade_execution_engine=TradeExecutionEngine(
            mode="SIMULATED"
        ),
        position_sizing_engine=PositionSizingEngine(
            minimum_contracts=1,
            maximum_contracts=20,
        ),
        account_risk_guard=AccountRiskGuard(
            daily_loss_limit=3000.0,
            max_trades_per_day=4,
            max_consecutive_losses=3,
            max_open_positions=1,
            max_risk_per_trade=1.0,
        ),
        execution_decision_engine=(
            ExecutionDecisionEngine(
                minimum_confidence=0.0,
            )
        ),
        confluence_engine_v2=ConfluenceEngineV2(),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if result["execution"]["accepted"]:
        assert result["account_risk"]["approved"] is False
        assert result["confluence_v2"]["decision"] == "BLOCK"
        assert (
            "account_risk_rejected"
            in result["confluence_v2"][
                "blocking_reasons"
            ]
        )
        assert "trade_execution" not in result


def test_confluence_v2_prevents_execution_for_low_grade():
    from backend.execution.execution_decision_engine import (
        ExecutionDecisionEngine,
    )
    from backend.execution.signal_execution_manager import (
        SignalExecutionManager,
    )
    from backend.execution.trade_execution_engine import (
        TradeExecutionEngine,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.risk_management.position_sizing_engine import (
        PositionSizingEngine,
    )

    class AlwaysLowConfluenceEngine(
        ConfluenceEngineV2
    ):
        def evaluate(
            self,
            **kwargs: object,
        ) -> dict[str, object]:
            return {
                "approved": False,
                "status": "REJECTED",
                "decision": "REJECT",
                "score": 40.0,
                "grade": "C",
                "contributions": {},
                "weights": {},
                "blocking_reasons": [],
            }

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_manager=SignalExecutionManager(
            cooldown_minutes=15
        ),
        trade_execution_engine=TradeExecutionEngine(
            mode="SIMULATED"
        ),
        position_sizing_engine=PositionSizingEngine(
            minimum_contracts=1,
            maximum_contracts=20,
        ),
        execution_decision_engine=(
            ExecutionDecisionEngine(
                minimum_confidence=0.0,
            )
        ),
        confluence_engine_v2=(
            AlwaysLowConfluenceEngine()
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    if result["execution"]["accepted"]:
        assert result["confluence_v2"]["grade"] == "C"
        assert result["confluence_v2"]["approved"] is False
        assert "trade_execution" not in result


def test_omits_confluence_v2_when_not_configured():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "confluence_v2" not in result


def test_includes_smart_money_v2_analysis():
    from backend.smart_money.smart_money_engine_v2 import (
        SmartMoneyEngineV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        smart_money_engine_v2=(
            SmartMoneyEngineV2()
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "smart_money_v2" in result

    smart_money = result[
        "smart_money_v2"
    ]

    assert "structure" in smart_money
    assert "fvg" in smart_money
    assert "order_block" in smart_money
    assert "price_zone" in smart_money
    assert "equal_levels" in smart_money

    assert smart_money["structure"][
        "event"
    ] in {
        "BOS",
        "CHOCH",
        "LIQUIDITY_SWEEP",
        "RANGE",
    }


def test_smart_money_v2_uses_latest_candles():
    from backend.smart_money.smart_money_engine_v2 import (
        SmartMoneyEngineV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        smart_money_engine_v2=(
            SmartMoneyEngineV2()
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    smart_money = result[
        "smart_money_v2"
    ]

    assert (
        smart_money["structure"][
            "close_price"
        ]
        == result["current_price"]
    )


def test_omits_smart_money_v2_when_not_configured():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "smart_money_v2" not in result


def test_rejects_invalid_smart_money_engine_v2():
    with pytest.raises(
        TypeError,
        match="smart_money_engine_v2",
    ):
        LiveMarketAnalysisService(
            candle_store=LiveCandleStore(),
            analysis_store=LiveAnalysisStore(),
            smart_money_engine_v2=object(),
        )


def test_confluence_v2_uses_smart_money_scores():
    from backend.execution.execution_decision_engine import (
        ExecutionDecisionEngine,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.smart_money.smart_money_engine_v2 import (
        SmartMoneyEngineV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_decision_engine=(
            ExecutionDecisionEngine(
                minimum_confidence=0.0,
            )
        ),
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        smart_money_engine_v2=(
            SmartMoneyEngineV2()
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "smart_money_v2" in result
    assert "confluence_v2" in result

    contributions = (
        result["confluence_v2"][
            "contributions"
        ]
    )

    assert (
        contributions["structure"]
        >= 7.5
    )

    assert (
        contributions["liquidity"]
        >= 5.0
    )

    assert (
        contributions["fvg"]
        >= 5.0
    )


def test_strong_smart_money_structure_raises_score():
    from backend.execution.execution_decision_engine import (
        ExecutionDecisionEngine,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.smart_money.smart_money_engine_v2 import (
        SmartMoneyEngineV2,
    )

    class StrongSmartMoneyEngine(
        SmartMoneyEngineV2
    ):
        def evaluate(
            self,
            **kwargs: object,
        ) -> dict[str, object]:
            return {
                "bos": True,
                "choch": False,
                "liquidity_sweep": True,
                "sweep_side": "BUY_SIDE",
                "event": "BOS",
                "direction": "BULLISH",
                "broken_level": 100.0,
                "previous_direction": "BULLISH",
                "previous_high": 100.0,
                "previous_low": 90.0,
                "current_high": 102.0,
                "current_low": 95.0,
                "close_price": 101.0,
            }

        def detect_fvg(
            self,
            **kwargs: object,
        ) -> dict[str, object]:
            return {
                "fvg": True,
                "direction": "BULLISH",
                "gap_low": 100.0,
                "gap_high": 102.0,
                "gap_size": 2.0,
            }

        def detect_order_block(
            self,
            **kwargs: object,
        ) -> dict[str, object]:
            return {
                "order_block": True,
                "direction": "BULLISH",
                "source_candle": "BEARISH",
                "zone_low": 95.0,
                "zone_high": 100.0,
                "zone_size": 5.0,
            }

        def evaluate_price_zone(
            self,
            **kwargs: object,
        ) -> dict[str, object]:
            return {
                "zone": "DISCOUNT",
                "equilibrium": 100.0,
                "position_percent": 25.0,
            }

        def detect_equal_levels(
            self,
            **kwargs: object,
        ) -> dict[str, object]:
            return {
                "equal_highs": True,
                "equal_lows": False,
                "liquidity_type": "BUY_SIDE",
                "high_difference": 0.10,
                "low_difference": 2.0,
                "tolerance": 0.25,
            }

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_decision_engine=(
            ExecutionDecisionEngine(
                minimum_confidence=0.0,
            )
        ),
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        smart_money_engine_v2=(
            StrongSmartMoneyEngine()
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    contributions = (
        result["confluence_v2"][
            "contributions"
        ]
    )

    assert contributions["structure"] == 15.0
    assert contributions["liquidity"] == 10.0
    assert contributions["fvg"] == 10.0


def test_weak_smart_money_structure_keeps_conservative_scores():
    from backend.execution.execution_decision_engine import (
        ExecutionDecisionEngine,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.smart_money.smart_money_engine_v2 import (
        SmartMoneyEngineV2,
    )

    class WeakSmartMoneyEngine(
        SmartMoneyEngineV2
    ):
        def evaluate(
            self,
            **kwargs: object,
        ) -> dict[str, object]:
            return {
                "bos": False,
                "choch": False,
                "liquidity_sweep": False,
                "sweep_side": None,
                "event": "RANGE",
                "direction": "RANGE",
                "broken_level": None,
                "previous_direction": None,
                "previous_high": 100.0,
                "previous_low": 90.0,
                "current_high": 99.0,
                "current_low": 91.0,
                "close_price": 95.0,
            }

        def detect_fvg(
            self,
            **kwargs: object,
        ) -> dict[str, object]:
            return {
                "fvg": False,
                "direction": "NONE",
                "gap_low": None,
                "gap_high": None,
                "gap_size": 0.0,
            }

        def detect_order_block(
            self,
            **kwargs: object,
        ) -> dict[str, object]:
            return {
                "order_block": False,
                "direction": "NONE",
                "source_candle": "DOJI",
                "zone_low": None,
                "zone_high": None,
                "zone_size": 0.0,
            }

        def evaluate_price_zone(
            self,
            **kwargs: object,
        ) -> dict[str, object]:
            return {
                "zone": "EQUILIBRIUM",
                "equilibrium": 100.0,
                "position_percent": 50.0,
            }

        def detect_equal_levels(
            self,
            **kwargs: object,
        ) -> dict[str, object]:
            return {
                "equal_highs": False,
                "equal_lows": False,
                "liquidity_type": "NONE",
                "high_difference": 1.0,
                "low_difference": 1.0,
                "tolerance": 0.25,
            }

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_decision_engine=(
            ExecutionDecisionEngine(
                minimum_confidence=0.0,
            )
        ),
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        smart_money_engine_v2=(
            WeakSmartMoneyEngine()
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    contributions = (
        result["confluence_v2"][
            "contributions"
        ]
    )

    assert contributions["structure"] <= 7.5
    assert contributions["liquidity"] <= 5.0
    assert contributions["fvg"] <= 5.0


def test_includes_probability_v2_result():
    from backend.execution.execution_decision_engine import (
        ExecutionDecisionEngine,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )
    from backend.market_analysis.market_regime_engine import (
        MarketRegimeEngine,
    )
    from backend.smart_money.smart_money_engine_v2 import (
        SmartMoneyEngineV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_decision_engine=(
            ExecutionDecisionEngine(
                minimum_confidence=0.0,
            )
        ),
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        market_regime_engine=(
            MarketRegimeEngine(
                trend_threshold=0.60,
                high_volatility_threshold=0.80,
                low_volatility_threshold=0.20,
                compression_threshold=0.15,
            )
        ),
        smart_money_engine_v2=(
            SmartMoneyEngineV2()
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "probability_v2" in result

    probability = result[
        "probability_v2"
    ]

    assert (
        0.0
        <= probability["probability"]
        <= 1.0
    )

    assert probability["confidence"] in {
        "VERY_HIGH",
        "HIGH",
        "MEDIUM",
        "LOW",
    }

    assert probability["grade"] in {
        "A+",
        "A",
        "B",
        "C",
    }

    assert probability["decision"] in {
        "EXECUTE",
        "WAIT",
        "REJECT",
        "BLOCK",
    }


def test_probability_v2_uses_confluence_score():
    from backend.execution.execution_decision_engine import (
        ExecutionDecisionEngine,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_decision_engine=(
            ExecutionDecisionEngine(
                minimum_confidence=0.0,
            )
        ),
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "confluence_v2" in result
    assert "probability_v2" in result

    probability = result[
        "probability_v2"
    ]

    expected_confluence_score = round(
        float(
            result["confluence_v2"][
                "score"
            ]
        )
        / 100.0,
        4,
    )

    assert (
        probability["inputs"][
            "confluence_score"
        ]
        == expected_confluence_score
    )


def test_probability_v2_respects_market_block():
    from backend.execution.execution_decision_engine import (
        ExecutionDecisionEngine,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )
    from backend.market_analysis.market_regime_engine import (
        MarketRegimeEngine,
    )

    class NoTradeMarketRegimeEngine(
        MarketRegimeEngine
    ):
        def evaluate(
            self,
            **kwargs: object,
        ) -> dict[str, object]:
            return {
                "regime": "NO_TRADE",
                "tradable": False,
                "direction": "NEUTRAL",
                "confidence": 1.0,
                "risk_multiplier": 0.0,
            }

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        execution_decision_engine=(
            ExecutionDecisionEngine(
                minimum_confidence=0.0,
            )
        ),
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        market_regime_engine=(
            NoTradeMarketRegimeEngine(
                trend_threshold=0.60,
                high_volatility_threshold=0.80,
                low_volatility_threshold=0.20,
                compression_threshold=0.15,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    probability = result[
        "probability_v2"
    ]

    assert probability["approved"] is False
    assert probability["decision"] == "BLOCK"
    assert probability["status"] == "BLOCKED"

    assert (
        "market_not_tradable"
        in probability[
            "blocking_reasons"
        ]
    )


def test_omits_probability_v2_when_not_configured():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "probability_v2" not in result


def test_rejects_invalid_probability_engine_v2():
    with pytest.raises(
        TypeError,
        match="probability_engine_v2",
    ):
        LiveMarketAnalysisService(
            candle_store=LiveCandleStore(),
            analysis_store=LiveAnalysisStore(),
            probability_engine_v2=object(),
        )


def test_includes_execution_v2_result():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )
    from backend.market_analysis.market_regime_engine import (
        MarketRegimeEngine,
    )
    from backend.risk_management.position_sizing_engine import (
        PositionSizingEngine,
    )
    from backend.smart_money.smart_money_engine_v2 import (
        SmartMoneyEngineV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
            )
        ),
        market_regime_engine=(
            MarketRegimeEngine(
                trend_threshold=0.60,
                high_volatility_threshold=0.80,
                low_volatility_threshold=0.20,
                compression_threshold=0.15,
            )
        ),
        position_sizing_engine=(
            PositionSizingEngine(
                minimum_contracts=1,
                maximum_contracts=20,
            )
        ),
        smart_money_engine_v2=(
            SmartMoneyEngineV2()
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "execution_v2" in result

    execution = result[
        "execution_v2"
    ]

    assert execution["decision"] in {
        "EXECUTE_LONG",
        "EXECUTE_SHORT",
        "WAIT",
        "BLOCK",
    }

    assert execution["direction"] in {
        "LONG",
        "SHORT",
    }

    assert (
        isinstance(
            execution["blocking_reasons"],
            list,
        )
    )

    assert (
        isinstance(
            execution["waiting_reasons"],
            list,
        )
    )


def test_execution_v2_uses_probability_v2():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "probability_v2" in result
    assert "execution_v2" in result

    execution = result[
        "execution_v2"
    ]

    assert (
        execution["inputs"][
            "probability"
        ]
        == result["probability_v2"][
            "probability"
        ]
    )


def test_execution_v2_blocks_when_probability_blocks():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )
    from backend.market_analysis.market_regime_engine import (
        MarketRegimeEngine,
    )

    class NoTradeMarketRegimeEngine(
        MarketRegimeEngine
    ):
        def evaluate(
            self,
            **kwargs: object,
        ) -> dict[str, object]:
            return {
                "regime": "NO_TRADE",
                "tradable": False,
                "direction": "NEUTRAL",
                "confidence": 1.0,
                "risk_multiplier": 0.0,
            }

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
            )
        ),
        market_regime_engine=(
            NoTradeMarketRegimeEngine(
                trend_threshold=0.60,
                high_volatility_threshold=0.80,
                low_volatility_threshold=0.20,
                compression_threshold=0.15,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    execution = result[
        "execution_v2"
    ]

    assert execution["approved"] is False
    assert execution["decision"] == "BLOCK"

    assert (
        "market_not_tradable"
        in execution[
            "blocking_reasons"
        ]
    )


def test_omits_execution_v2_when_not_configured():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "execution_v2" not in result


def test_rejects_invalid_execution_decision_engine_v2():
    with pytest.raises(
        TypeError,
        match="execution_decision_engine_v2",
    ):
        LiveMarketAnalysisService(
            candle_store=LiveCandleStore(),
            analysis_store=LiveAnalysisStore(),
            execution_decision_engine_v2=object(),
        )


def test_includes_trade_plan_v2_result():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
            )
        ),
        trade_planner_v2=(
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "execution_v2" in result
    assert "trade_plan_v2" in result

    trade_plan = result[
        "trade_plan_v2"
    ]

    assert trade_plan["status"] in {
        "ACTIVE",
        "INACTIVE",
    }

    assert (
        trade_plan["approved"]
        is (
            result["execution_v2"][
                "approved"
            ]
        )
    )


def test_trade_plan_v2_uses_execution_decision():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
            )
        ),
        trade_planner_v2=(
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert (
        result["trade_plan_v2"][
            "source_decision"
        ]
        == result["execution_v2"][
            "decision"
        ]
    )


def test_trade_plan_v2_uses_probability_and_confluence():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
            )
        ),
        trade_planner_v2=(
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    trade_plan = result[
        "trade_plan_v2"
    ]

    probability = result[
        "probability_v2"
    ]

    assert (
        trade_plan["probability"]
        == probability["probability"]
    )

    assert (
        trade_plan["confluence_score"]
        == probability["inputs"][
            "confluence_score"
        ]
    )

    assert (
        trade_plan["grade"]
        == probability["grade"]
    )


def test_inactive_trade_plan_v2_when_execution_waits():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.99,
                very_high_threshold=0.99,
                high_threshold=0.95,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.99,
                minimum_confluence_score=0.99,
            )
        ),
        trade_planner_v2=(
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert (
        result["execution_v2"][
            "decision"
        ]
        == "WAIT"
    )

    assert (
        result["trade_plan_v2"][
            "approved"
        ]
        is False
    )

    assert (
        result["trade_plan_v2"][
            "status"
        ]
        == "INACTIVE"
    )


def test_omits_trade_plan_v2_when_not_configured():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "trade_plan_v2" not in result


def test_rejects_invalid_trade_planner_v2():
    with pytest.raises(
        TypeError,
        match="trade_planner_v2",
    ):
        LiveMarketAnalysisService(
            candle_store=LiveCandleStore(),
            analysis_store=LiveAnalysisStore(),
            trade_planner_v2=object(),
        )


def test_includes_trade_validation_v2_result():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.execution.trade_validator_v2 import (
        TradeValidatorV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
            )
        ),
        trade_planner_v2=(
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        ),
        trade_validator_v2=(
            TradeValidatorV2(
                minimum_reward_risk_ratio=2.0,
                minimum_stop_points=2.0,
                maximum_stop_points=50.0,
                maximum_spread_points=1.0,
                minimum_atr_points=3.0,
                maximum_signal_age_seconds=30,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "trade_plan_v2" in result
    assert "trade_validation_v2" in result

    validation = result[
        "trade_validation_v2"
    ]

    assert validation["decision"] in {
        "ALLOW_EXECUTION",
        "BLOCK",
    }

    assert validation["status"] in {
        "VALID",
        "INVALID",
    }

    assert isinstance(
        validation["blocking_reasons"],
        list,
    )

    assert isinstance(
        validation["warnings"],
        list,
    )


def test_trade_validation_v2_uses_trade_plan_v2():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.execution.trade_validator_v2 import (
        TradeValidatorV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
            )
        ),
        trade_planner_v2=(
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        ),
        trade_validator_v2=(
            TradeValidatorV2(
                minimum_reward_risk_ratio=2.0,
                minimum_stop_points=2.0,
                maximum_stop_points=50.0,
                maximum_spread_points=1.0,
                minimum_atr_points=3.0,
                maximum_signal_age_seconds=30,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    validation = result[
        "trade_validation_v2"
    ]

    assert (
        validation["source_trade_plan_status"]
        == result["trade_plan_v2"][
            "status"
        ]
    )

    assert (
        validation["source_trade_plan_approved"]
        == result["trade_plan_v2"][
            "approved"
        ]
    )


def test_trade_validation_v2_blocks_inactive_plan():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.execution.trade_validator_v2 import (
        TradeValidatorV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.99,
                very_high_threshold=0.99,
                high_threshold=0.95,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.99,
                minimum_confluence_score=0.99,
            )
        ),
        trade_planner_v2=(
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        ),
        trade_validator_v2=(
            TradeValidatorV2(
                minimum_reward_risk_ratio=2.0,
                minimum_stop_points=2.0,
                maximum_stop_points=50.0,
                maximum_spread_points=1.0,
                minimum_atr_points=3.0,
                maximum_signal_age_seconds=30,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert (
        result["trade_plan_v2"][
            "approved"
        ]
        is False
    )

    assert (
        result["trade_validation_v2"][
            "approved"
        ]
        is False
    )

    assert (
        result["trade_validation_v2"][
            "decision"
        ]
        == "BLOCK"
    )

    assert (
        "trade_plan_not_approved"
        in result["trade_validation_v2"][
            "blocking_reasons"
        ]
    )


def test_omits_trade_validation_v2_when_not_configured():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "trade_validation_v2" not in result


def test_rejects_invalid_trade_validator_v2():
    with pytest.raises(
        TypeError,
        match="trade_validator_v2",
    ):
        LiveMarketAnalysisService(
            candle_store=LiveCandleStore(),
            analysis_store=LiveAnalysisStore(),
            trade_validator_v2=object(),
        )


def test_includes_signal_v2_result():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.execution.trade_validator_v2 import (
        TradeValidatorV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )
    from backend.signals.signal_generator_v2 import (
        SignalGeneratorV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
            )
        ),
        trade_planner_v2=(
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        ),
        trade_validator_v2=(
            TradeValidatorV2(
                minimum_reward_risk_ratio=2.0,
                minimum_stop_points=2.0,
                maximum_stop_points=50.0,
                maximum_spread_points=1.0,
                minimum_atr_points=3.0,
                maximum_signal_age_seconds=30,
            )
        ),
        signal_generator_v2=(
            SignalGeneratorV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
                allowed_grades={
                    "A+",
                    "A",
                },
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "trade_plan_v2" in result
    assert "trade_validation_v2" in result
    assert "signal_v2" in result

    signal = result[
        "signal_v2"
    ]

    assert signal["decision"] in {
        "SEND_SIGNAL",
        "DO_NOT_SEND",
    }

    assert signal["status"] in {
        "READY",
        "BLOCKED",
    }

    assert signal["symbol"] == "NQ"
    assert signal["timeframe"] == "5M"

    assert isinstance(
        signal["blocking_reasons"],
        list,
    )

    assert isinstance(
        signal["warnings"],
        list,
    )


def test_signal_v2_uses_trade_plan_and_validation():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.execution.trade_validator_v2 import (
        TradeValidatorV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )
    from backend.signals.signal_generator_v2 import (
        SignalGeneratorV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
            )
        ),
        trade_planner_v2=(
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        ),
        trade_validator_v2=(
            TradeValidatorV2(
                minimum_reward_risk_ratio=2.0,
                minimum_stop_points=2.0,
                maximum_stop_points=50.0,
                maximum_spread_points=1.0,
                minimum_atr_points=3.0,
                maximum_signal_age_seconds=30,
            )
        ),
        signal_generator_v2=(
            SignalGeneratorV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
                allowed_grades={
                    "A+",
                    "A",
                },
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    signal = result[
        "signal_v2"
    ]

    trade_plan = result[
        "trade_plan_v2"
    ]

    validation = result[
        "trade_validation_v2"
    ]

    assert (
        signal["direction"]
        == trade_plan["direction"]
    )

    assert (
        signal["entry_price"]
        == trade_plan["entry_price"]
    )

    assert (
        signal["stop_loss"]
        == trade_plan["stop_loss"]
    )

    assert (
        signal["take_profit"]
        == trade_plan["take_profit"]
    )

    assert (
        signal["probability"]
        == trade_plan["probability"]
    )

    assert (
        signal["warnings"]
        == validation["warnings"]
    )


def test_signal_v2_blocks_when_validation_blocks():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.execution.trade_validator_v2 import (
        TradeValidatorV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )
    from backend.signals.signal_generator_v2 import (
        SignalGeneratorV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.99,
                very_high_threshold=0.99,
                high_threshold=0.95,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.99,
                minimum_confluence_score=0.99,
            )
        ),
        trade_planner_v2=(
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        ),
        trade_validator_v2=(
            TradeValidatorV2(
                minimum_reward_risk_ratio=2.0,
                minimum_stop_points=2.0,
                maximum_stop_points=50.0,
                maximum_spread_points=1.0,
                minimum_atr_points=3.0,
                maximum_signal_age_seconds=30,
            )
        ),
        signal_generator_v2=(
            SignalGeneratorV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
                allowed_grades={
                    "A+",
                    "A",
                },
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert (
        result["trade_validation_v2"][
            "approved"
        ]
        is False
    )

    assert (
        result["signal_v2"][
            "approved"
        ]
        is False
    )

    assert (
        result["signal_v2"][
            "decision"
        ]
        == "DO_NOT_SEND"
    )


def test_omits_signal_v2_when_not_configured():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "signal_v2" not in result


def test_rejects_invalid_signal_generator_v2():
    with pytest.raises(
        TypeError,
        match="signal_generator_v2",
    ):
        LiveMarketAnalysisService(
            candle_store=LiveCandleStore(),
            analysis_store=LiveAnalysisStore(),
            signal_generator_v2=object(),
        )


def test_includes_paper_execution_v2_result():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.execution_manager_v2 import (
        ExecutionManagerV2,
    )
    from backend.execution.paper_execution_engine_v2 import (
        PaperExecutionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.execution.trade_validator_v2 import (
        TradeValidatorV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )
    from backend.signals.signal_generator_v2 import (
        SignalGeneratorV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
            )
        ),
        trade_planner_v2=(
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        ),
        trade_validator_v2=(
            TradeValidatorV2(
                minimum_reward_risk_ratio=2.0,
                minimum_stop_points=2.0,
                maximum_stop_points=50.0,
                maximum_spread_points=1.0,
                minimum_atr_points=3.0,
                maximum_signal_age_seconds=30,
            )
        ),
        signal_generator_v2=(
            SignalGeneratorV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
                allowed_grades={
                    "A+",
                    "A",
                },
            )
        ),
        execution_manager_v2=(
            ExecutionManagerV2(
                execution_mode="PAPER",
                maximum_contracts=20,
            )
        ),
        paper_execution_engine_v2=(
            PaperExecutionEngineV2(
                fill_market_orders_immediately=True,
                slippage_points=0.25,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "prepared_order_v2" in result
    assert "paper_execution_v2" in result

    execution = result[
        "paper_execution_v2"
    ]

    assert execution["status"] in {
        "FILLED",
        "SUBMITTED",
        "REJECTED",
    }

    assert isinstance(
        execution["rejection_reasons"],
        list,
    )

    assert execution["execution_mode"] == "PAPER"


def test_paper_execution_v2_uses_prepared_order():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.execution_manager_v2 import (
        ExecutionManagerV2,
    )
    from backend.execution.paper_execution_engine_v2 import (
        PaperExecutionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.execution.trade_validator_v2 import (
        TradeValidatorV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )
    from backend.signals.signal_generator_v2 import (
        SignalGeneratorV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.80,
                very_high_threshold=0.90,
                high_threshold=0.80,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
            )
        ),
        trade_planner_v2=(
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        ),
        trade_validator_v2=(
            TradeValidatorV2(
                minimum_reward_risk_ratio=2.0,
                minimum_stop_points=2.0,
                maximum_stop_points=50.0,
                maximum_spread_points=1.0,
                minimum_atr_points=3.0,
                maximum_signal_age_seconds=30,
            )
        ),
        signal_generator_v2=(
            SignalGeneratorV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
                allowed_grades={
                    "A+",
                    "A",
                },
            )
        ),
        execution_manager_v2=(
            ExecutionManagerV2(
                execution_mode="PAPER",
                maximum_contracts=20,
            )
        ),
        paper_execution_engine_v2=(
            PaperExecutionEngineV2(
                fill_market_orders_immediately=True,
                slippage_points=0.25,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    prepared_order = result[
        "prepared_order_v2"
    ]

    execution = result[
        "paper_execution_v2"
    ]

    assert (
        execution["symbol"]
        == prepared_order["symbol"]
    )

    assert (
        execution["side"]
        == prepared_order["side"]
    )

    assert (
        execution["quantity"]
        == prepared_order["quantity"]
    )

    assert (
        execution["stop_loss"]
        == prepared_order["stop_loss"]
    )

    assert (
        execution["take_profit"]
        == prepared_order["take_profit"]
    )


def test_paper_execution_v2_rejects_blocked_order():
    from backend.execution.execution_decision_engine_v2 import (
        ExecutionDecisionEngineV2,
    )
    from backend.execution.execution_manager_v2 import (
        ExecutionManagerV2,
    )
    from backend.execution.paper_execution_engine_v2 import (
        PaperExecutionEngineV2,
    )
    from backend.execution.trade_planner_v2 import (
        TradePlannerV2,
    )
    from backend.execution.trade_validator_v2 import (
        TradeValidatorV2,
    )
    from backend.intelligence.confluence_engine_v2 import (
        ConfluenceEngineV2,
    )
    from backend.intelligence.probability_engine_v2 import (
        ProbabilityEngineV2,
    )
    from backend.signals.signal_generator_v2 import (
        SignalGeneratorV2,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        confluence_engine_v2=(
            ConfluenceEngineV2()
        ),
        probability_engine_v2=(
            ProbabilityEngineV2(
                minimum_approval_probability=0.99,
                very_high_threshold=0.99,
                high_threshold=0.95,
                medium_threshold=0.65,
            )
        ),
        execution_decision_engine_v2=(
            ExecutionDecisionEngineV2(
                minimum_probability=0.99,
                minimum_confluence_score=0.99,
            )
        ),
        trade_planner_v2=(
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        ),
        trade_validator_v2=(
            TradeValidatorV2(
                minimum_reward_risk_ratio=2.0,
                minimum_stop_points=2.0,
                maximum_stop_points=50.0,
                maximum_spread_points=1.0,
                minimum_atr_points=3.0,
                maximum_signal_age_seconds=30,
            )
        ),
        signal_generator_v2=(
            SignalGeneratorV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
                allowed_grades={
                    "A+",
                    "A",
                },
            )
        ),
        execution_manager_v2=(
            ExecutionManagerV2(
                execution_mode="PAPER",
                maximum_contracts=20,
            )
        ),
        paper_execution_engine_v2=(
            PaperExecutionEngineV2(
                fill_market_orders_immediately=True,
                slippage_points=0.25,
            )
        ),
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert (
        result["prepared_order_v2"][
            "approved"
        ]
        is False
    )

    assert (
        result["paper_execution_v2"][
            "accepted"
        ]
        is False
    )

    assert (
        result["paper_execution_v2"][
            "status"
        ]
        == "REJECTED"
    )


def test_omits_paper_execution_v2_when_not_configured():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert "paper_execution_v2" not in result


def test_rejects_invalid_paper_execution_engine_v2():
    with pytest.raises(
        TypeError,
        match="paper_execution_engine_v2",
    ):
        LiveMarketAnalysisService(
            candle_store=LiveCandleStore(),
            analysis_store=LiveAnalysisStore(),
            paper_execution_engine_v2=object(),
        )
