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
