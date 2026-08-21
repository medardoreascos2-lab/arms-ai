from backend.backtesting.strategy_backtest_factory_v2 import (
    build_lifecycle,
)


def test_backtest_execution_uses_active_account_limits():
    lifecycle = build_lifecycle()

    execution = lifecycle.execution_manager

    expected = {
        "NQ": 5,
        "MNQ": 50,
        "ES": 5,
        "MES": 50,
    }

    for symbol, expected_limit in expected.items():
        assert (
            execution.get_contract_limit(symbol)
            == expected_limit
        )


def test_backtest_execution_fallback_is_safe_mini_limit():
    lifecycle = build_lifecycle()

    execution = lifecycle.execution_manager

    assert execution.maximum_contracts == 5


def test_backtest_allows_fifty_mnq_by_contract_rule():
    lifecycle = build_lifecycle()

    execution = lifecycle.execution_manager

    signal = {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "MNQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "contracts": 50,
        "probability": 0.95,
        "confluence_score": 0.95,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": "MNQ LONG",
    }

    result = execution.prepare_order(
        signal=signal,
        order_type="MARKET",
    )

    assert (
        "maximum_contracts_exceeded"
        not in result["blocking_reasons"]
    )


def test_backtest_blocks_six_nq_by_contract_rule():
    lifecycle = build_lifecycle()

    execution = lifecycle.execution_manager

    signal = {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "contracts": 6,
        "probability": 0.95,
        "confluence_score": 0.95,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": "NQ LONG",
    }

    result = execution.prepare_order(
        signal=signal,
        order_type="MARKET",
    )

    assert result["approved"] is False

    assert (
        "maximum_contracts_exceeded"
        in result["blocking_reasons"]
    )
