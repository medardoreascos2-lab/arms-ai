import json

from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)
from backend.execution.execution_risk_gate_v1 import (
    ExecutionRiskGateV1,
)
from backend.risk.multi_account_risk_engine_v2 import (
    MultiAccountRiskEngineV2,
)
from backend.risk.trade_risk_validator_v2 import (
    TradeRiskValidatorV2,
)


def _build_shared_execution_chain(
    *,
    config_path=None,
):
    account_manager = AccountConfigManagerV2(
        config_path=config_path,
    )

    risk_engine = MultiAccountRiskEngineV2(
        account_manager=account_manager,
    )

    validator = TradeRiskValidatorV2(
        risk_engine=risk_engine,
    )

    gate = ExecutionRiskGateV1(
        validator=validator,
    )

    return (
        account_manager,
        risk_engine,
        validator,
        gate,
    )


def test_shared_execution_chain_preserves_account_manager_identity():
    (
        account_manager,
        risk_engine,
        validator,
        gate,
    ) = _build_shared_execution_chain()

    assert (
        risk_engine.account_manager
        is account_manager
    )

    assert (
        validator.risk_engine
        is risk_engine
    )

    assert (
        gate.validator
        is validator
    )


def test_account_switch_is_visible_to_execution_validator(
    tmp_path,
):
    baseline_manager = AccountConfigManagerV2()

    initial_name = (
        baseline_manager
        .get_active_account_name()
    )

    config_path = (
        tmp_path
        / "accounts.json"
    )

    config_path.write_text(
        json.dumps(
            {
                "active_account":
                    initial_name,
            },
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )

    (
        account_manager,
        risk_engine,
        validator,
        gate,
    ) = _build_shared_execution_chain(
        config_path=config_path,
    )

    available = (
        account_manager
        .get_available_accounts()
    )

    assert available

    alternate_names = [
        name
        for name in available
        if name != initial_name
    ]

    assert alternate_names

    target_name = alternate_names[0]

    account_manager.set_active_account(
        target_name
    )

    assert (
        risk_engine
        .account_manager
        .get_active_account_name()
        == target_name
    )

    assert (
        validator
        .risk_engine
        .account_manager
        .get_active_account_name()
        == target_name
    )

    assert (
        gate
        .validator
        .risk_engine
        .account_manager
        .get_active_account_name()
        == target_name
    )

    persisted = json.loads(
        config_path.read_text(
            encoding="utf-8",
        )
    )

    assert (
        persisted["active_account"]
        == target_name
    )


def test_default_app_wires_final_gate_to_shared_account_manager():
    from backend.api.app import create_app

    app = create_app()

    lifecycle = (
        app.state
        .trade_lifecycle_service_v2
    )

    runtime_manager = (
        app.state
        .account_config_manager_v2
    )

    gate = (
        lifecycle
        .execution_risk_gate_v1
    )

    assert gate is not None

    assert (
        gate
        .validator
        .risk_engine
        .account_manager
        is runtime_manager
    )


def test_account_manager_api_switch_updates_final_gate_policy(
    tmp_path,
):
    from fastapi.testclient import TestClient

    from backend.api.app import create_app

    baseline_manager = (
        AccountConfigManagerV2()
    )

    initial_name = (
        baseline_manager
        .get_active_account_name()
    )

    available = (
        baseline_manager
        .get_available_accounts()
    )

    alternate_names = [
        name
        for name in available
        if name != initial_name
    ]

    assert alternate_names

    target_name = alternate_names[0]

    config_path = (
        tmp_path
        / "accounts.json"
    )

    config_path.write_text(
        json.dumps(
            {
                "active_account":
                    initial_name,
            },
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )

    runtime_manager = (
        AccountConfigManagerV2(
            config_path=config_path,
        )
    )

    app = create_app(
        account_config_manager_v2=(
            runtime_manager
        )
    )

    lifecycle = (
        app.state
        .trade_lifecycle_service_v2
    )

    gate = (
        lifecycle
        .execution_risk_gate_v1
    )

    assert (
        gate
        .validator
        .risk_engine
        .account_manager
        is runtime_manager
    )

    client = TestClient(app)

    response = client.post(
        "/api/v2/dashboard/"
        "account-manager/switch",
        params={
            "account_name":
                target_name,
        },
    )

    assert response.status_code == 200

    assert (
        response.json()[
            "active_account"
        ]
        == target_name
    )

    assert (
        runtime_manager
        .get_active_account_name()
        == target_name
    )

    assert (
        gate
        .validator
        .risk_engine
        .account_manager
        .get_active_account_name()
        == target_name
    )

    persisted = json.loads(
        config_path.read_text(
            encoding="utf-8",
        )
    )

    assert (
        persisted["active_account"]
        == target_name
    )
