from backend.api.app import create_app


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


def test_runtime_exposure_has_no_raw_contract_caps():
    app = create_app()

    exposure = (
        app.state
        .trade_lifecycle_service_v2
        .exposure_manager_v2
    )

    assert exposure.maximum_total_contracts is None
    assert exposure.maximum_symbol_contracts is None


def test_fifty_mnq_low_risk_passes_exposure_layer():
    app = create_app()

    exposure = (
        app.state
        .trade_lifecycle_service_v2
        .exposure_manager_v2
    )

    result = exposure.evaluate(
        open_positions=[],
        candidate_symbol="MNQ",
        candidate_contracts=50,
        candidate_stop_points=1.0,
        candidate_point_value=2.0,
    )

    assert result["candidate_risk"] == 100.0
    assert result["approved"] is True

    assert (
        "maximum_total_contracts_exceeded"
        not in result["blocking_reasons"]
    )

    assert (
        "maximum_symbol_contracts_exceeded"
        not in result["blocking_reasons"]
    )


def test_fifty_mnq_high_risk_is_blocked_by_risk():
    app = create_app()

    exposure = (
        app.state
        .trade_lifecycle_service_v2
        .exposure_manager_v2
    )

    result = exposure.evaluate(
        open_positions=[],
        candidate_symbol="MNQ",
        candidate_contracts=50,
        candidate_stop_points=10.0,
        candidate_point_value=2.0,
    )

    assert result["candidate_risk"] == 1000.0
    assert result["approved"] is False

    assert (
        "maximum_total_open_risk_exceeded"
        in result["blocking_reasons"]
    )

    assert (
        "maximum_symbol_open_risk_exceeded"
        in result["blocking_reasons"]
    )

    assert (
        "maximum_total_contracts_exceeded"
        not in result["blocking_reasons"]
    )

    assert (
        "maximum_symbol_contracts_exceeded"
        not in result["blocking_reasons"]
    )


def test_six_nq_remains_blocked_by_firm_contract_rule():
    app = create_app()

    execution = (
        app.state
        .trade_lifecycle_service_v2
        .execution_manager
    )

    result = execution.prepare_order(
        signal=build_signal(
            symbol="NQ",
            contracts=16,
        ),
        order_type="MARKET",
    )

    assert result["approved"] is False

    assert (
        "maximum_contracts_exceeded"
        in result["blocking_reasons"]
    )


def test_fifty_mnq_is_allowed_by_firm_contract_rule():
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
