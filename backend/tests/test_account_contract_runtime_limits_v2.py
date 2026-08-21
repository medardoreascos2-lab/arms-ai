from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)
from backend.instruments.instrument_profile_engine import (
    InstrumentProfileEngine,
)


def test_active_account_resolves_contract_limits_by_instrument():
    manager = AccountConfigManagerV2()
    profile = manager.get_active_account()

    instruments = InstrumentProfileEngine()

    mnq = instruments.get_profile(
        symbol="MNQ",
    )
    nq = instruments.get_profile(
        symbol="NQ",
    )

    assert mnq["contract_class"] == "MICRO"
    assert nq["contract_class"] == "MINI"

    assert (
        profile.get_contract_limit(
            mnq["contract_class"],
        )
        == 50
    )

    assert (
        profile.get_contract_limit(
            nq["contract_class"],
        )
        == 5
    )


def test_runtime_must_not_use_single_contract_limit_for_mini_and_micro():
    manager = AccountConfigManagerV2()
    profile = manager.get_active_account()

    micro_limit = profile.get_contract_limit(
        "MICRO",
    )
    mini_limit = profile.get_contract_limit(
        "MINI",
    )

    assert micro_limit == 50
    assert mini_limit == 5
    assert micro_limit != mini_limit


def test_trade_lifecycle_runtime_has_no_legacy_twenty_contract_limit():
    from backend.api.app import create_app

    app = create_app()

    lifecycle = (
        app.state.trade_lifecycle_service_v2
    )

    execution_manager = (
        lifecycle.execution_manager
    )

    risk_manager = (
        lifecycle.risk_manager_v2
    )

    legacy_twenty = []

    if (
        execution_manager.maximum_contracts
        == 20
    ):
        legacy_twenty.append(
            (
                "execution_manager",
                execution_manager
                .__class__.__name__,
                execution_manager
                .maximum_contracts,
            )
        )

    if (
        risk_manager.maximum_contracts
        == 20
    ):
        legacy_twenty.append(
            (
                "risk_manager_v2",
                risk_manager
                .__class__.__name__,
                risk_manager
                .maximum_contracts,
            )
        )

    assert legacy_twenty == [], (
        "Trade lifecycle todavía usa "
        "maximum_contracts=20: "
        f"{legacy_twenty}"
    )
