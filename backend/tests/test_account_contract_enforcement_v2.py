from backend.api.app import create_app


def build_signal(
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
        "summary": (
            f"{symbol} LONG ENTRY 100 "
            "SL 95 TP 110"
        ),
    }


def test_execution_blocks_six_nq_contracts():
    app = create_app()

    execution = (
        app.state
        .trade_lifecycle_service_v2
        .execution_manager
    )

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


def test_execution_allows_fifty_mnq_contracts():
    app = create_app()

    execution = (
        app.state
        .trade_lifecycle_service_v2
        .execution_manager
    )

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


def test_risk_manager_uses_symbol_aware_limits():
    app = create_app()

    risk = (
        app.state
        .trade_lifecycle_service_v2
        .risk_manager_v2
    )

    nq_limit = risk.get_contract_limit("NQ")
    mnq_limit = risk.get_contract_limit("MNQ")

    assert nq_limit == 5
    assert mnq_limit == 50
