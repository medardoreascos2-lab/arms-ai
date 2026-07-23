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
