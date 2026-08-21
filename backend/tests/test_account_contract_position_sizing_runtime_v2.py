from backend.api.app import create_app


def test_runtime_position_sizing_uses_active_account_limits():
    app = create_app()

    engine = app.state.position_sizing_engine

    expected = {
        "NQ": 5,
        "MNQ": 50,
        "ES": 5,
        "MES": 50,
    }

    for symbol, expected_limit in expected.items():
        assert (
            engine.get_contract_limit(symbol)
            == expected_limit
        )


def test_runtime_position_sizing_caps_nq_at_five():
    app = create_app()

    engine = app.state.position_sizing_engine

    result = engine.calculate_for_symbol(
        symbol="NQ",
        account_balance=1_000_000.0,
        risk_percent=10.0,
        entry_price=100.0,
        stop_loss=99.0,
    )

    assert result["contracts"] == 5
    assert result["maximum_contracts"] == 5
    assert result["status"] == "CAPPED_AT_MAXIMUM"


def test_runtime_position_sizing_caps_mnq_at_fifty():
    app = create_app()

    engine = app.state.position_sizing_engine

    result = engine.calculate_for_symbol(
        symbol="MNQ",
        account_balance=1_000_000.0,
        risk_percent=10.0,
        entry_price=100.0,
        stop_loss=99.0,
    )

    assert result["contracts"] == 50
    assert result["maximum_contracts"] == 50
    assert result["status"] == "CAPPED_AT_MAXIMUM"


def test_runtime_position_sizing_caps_es_at_five():
    app = create_app()

    engine = app.state.position_sizing_engine

    result = engine.calculate_for_symbol(
        symbol="ES",
        account_balance=1_000_000.0,
        risk_percent=10.0,
        entry_price=100.0,
        stop_loss=99.0,
    )

    assert result["contracts"] == 5
    assert result["maximum_contracts"] == 5
    assert result["status"] == "CAPPED_AT_MAXIMUM"


def test_runtime_position_sizing_caps_mes_at_fifty():
    app = create_app()

    engine = app.state.position_sizing_engine

    result = engine.calculate_for_symbol(
        symbol="MES",
        account_balance=1_000_000.0,
        risk_percent=10.0,
        entry_price=100.0,
        stop_loss=99.0,
    )

    assert result["contracts"] == 50
    assert result["maximum_contracts"] == 50
    assert result["status"] == "CAPPED_AT_MAXIMUM"


def test_legacy_position_sizing_fallback_remains_available():
    from backend.risk_management.position_sizing_engine import (
        PositionSizingEngine,
    )
    from backend.instruments.instrument_profile_engine import (
        InstrumentProfileEngine,
    )

    engine = PositionSizingEngine(
        minimum_contracts=1,
        maximum_contracts=20,
        instrument_profile_engine=(
            InstrumentProfileEngine()
        ),
    )

    result = engine.calculate_for_symbol(
        symbol="MNQ",
        account_balance=1_000_000.0,
        risk_percent=10.0,
        entry_price=100.0,
        stop_loss=99.0,
    )

    assert result["maximum_contracts"] == 20
    assert result["contracts"] == 20
