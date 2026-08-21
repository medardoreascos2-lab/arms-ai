from backend.services.runtime_context_v2 import (
    build_runtime_context,
)


def build_signal(
    *,
    symbol: str,
    contracts: int,
) -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": symbol,
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "contracts": contracts,
        "probability": 0.95,
        "confluence_score": 0.95,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": f"{symbol} LONG",
    }


def test_default_runtime_context_uses_active_account_limits():
    context = build_runtime_context()

    execution = context.execution_manager

    expected = {
        "NQ": 5,
        "MNQ": 50,
        "ES": 5,
        "MES": 50,
    }

    assert execution.maximum_contracts == 5

    assert (
        execution.contract_limit_resolver
        is not None
    )

    for symbol, expected_limit in expected.items():
        assert (
            execution.get_contract_limit(symbol)
            == expected_limit
        )


def test_default_runtime_context_blocks_six_nq():
    context = build_runtime_context()

    execution = context.execution_manager

    result = execution.prepare_order(
        signal=build_signal(
            symbol="NQ",
            contracts=6,
        ),
        order_type="MARKET",
    )

    assert result["approved"] is False

    assert (
        "maximum_contracts_exceeded"
        in result["blocking_reasons"]
    )


def test_default_runtime_context_allows_fifty_mnq():
    context = build_runtime_context()

    execution = context.execution_manager

    result = execution.prepare_order(
        signal=build_signal(
            symbol="MNQ",
            contracts=50,
        ),
        order_type="MARKET",
    )

    assert (
        "maximum_contracts_exceeded"
        not in result["blocking_reasons"]
    )


def test_explicit_runtime_contract_override_is_preserved():
    context = build_runtime_context(
        maximum_contracts=7,
    )

    execution = context.execution_manager

    assert execution.maximum_contracts == 7

    assert (
        execution.contract_limit_resolver
        is None
    )

    for symbol in (
        "NQ",
        "MNQ",
        "ES",
        "MES",
    ):
        assert (
            execution.get_contract_limit(symbol)
            == 7
        )
