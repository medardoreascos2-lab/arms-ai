from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)
from backend.instruments.instrument_profile_engine import (
    InstrumentProfileEngine,
)


def resolve_limit(symbol: str) -> int:
    manager = AccountConfigManagerV2()
    account = manager.get_active_account()

    instruments = InstrumentProfileEngine()

    profile = instruments.get_profile(
        symbol=symbol,
    )

    return account.get_contract_limit(
        profile["contract_class"],
    )


def test_account_contract_resolves_nq_and_mnq_differently():
    assert resolve_limit("NQ") == 15
    assert resolve_limit("MNQ") == 150


def test_account_contract_resolves_es_and_mes_differently():
    assert resolve_limit("ES") == 15
    assert resolve_limit("MES") == 150


def test_runtime_execution_manager_exposes_symbol_aware_limit():
    from backend.api.app import create_app

    app = create_app()

    lifecycle = (
        app.state.trade_lifecycle_service_v2
    )

    execution = lifecycle.execution_manager

    assert hasattr(
        execution,
        "get_contract_limit",
    ), (
        "ExecutionManagerV2 todavía no expone "
        "get_contract_limit(symbol)"
    )

    assert execution.get_contract_limit("NQ") == 15
    assert execution.get_contract_limit("MNQ") == 150
    assert execution.get_contract_limit("ES") == 15
    assert execution.get_contract_limit("MES") == 150


def test_runtime_risk_manager_exposes_symbol_aware_limit():
    from backend.api.app import create_app

    app = create_app()

    lifecycle = (
        app.state.trade_lifecycle_service_v2
    )

    risk = lifecycle.risk_manager_v2

    assert hasattr(
        risk,
        "get_contract_limit",
    ), (
        "RiskManagerV2 todavía no expone "
        "get_contract_limit(symbol)"
    )

    assert risk.get_contract_limit("NQ") == 15
    assert risk.get_contract_limit("MNQ") == 150
    assert risk.get_contract_limit("ES") == 15
    assert risk.get_contract_limit("MES") == 150


def test_legacy_maximum_contracts_remains_conservative():
    from backend.api.app import create_app

    app = create_app()

    lifecycle = (
        app.state.trade_lifecycle_service_v2
    )

    assert (
        lifecycle.execution_manager
        .maximum_contracts
        == 15
    )

    assert (
        lifecycle.risk_manager_v2
        .maximum_contracts
        == 15
    )
