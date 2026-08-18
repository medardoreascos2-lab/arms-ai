from backend.accounts.account_registry_v1 import (
    AccountRegistryV1,
)

from backend.accounts.profiles.topstep_profiles import (
    TopstepProfiles,
)

from backend.risk.multi_account_risk_engine_v2 import (
    MultiAccountRiskEngineV2,
)

from backend.risk.trade_risk_validator_v2 import (
    TradeRiskValidatorV2,
)


class FakeAccountManager:

    def __init__(
        self,
        account_name,
    ):

        self.account_name = (
            account_name
        )

        self.registry = (
            AccountRegistryV1()
        )


    def get_active_account(
        self,
    ):

        return (
            self.registry
            .get_account(
                self.account_name
            )
        )


    def get_active_account_name(
        self,
    ):

        return self.account_name


def build_validator(
    account_name,
):

    risk_engine = (
        MultiAccountRiskEngineV2(
            account_manager=(
                FakeAccountManager(
                    account_name
                )
            )
        )
    )

    return TradeRiskValidatorV2(
        risk_engine=risk_engine
    )


def test_topstep_50k_profile():

    profile = (
        TopstepProfiles
        .account_50k()
    )

    assert profile.account_size == 50000
    assert profile.profit_target == 3000.0
    assert profile.maximum_loss_limit == 2000.0
    assert profile.max_mini_contracts == 5
    assert profile.max_micro_contracts == 50
    assert profile.account_stage == "TRADING_COMBINE"


def test_topstep_150k_profile():

    profile = (
        TopstepProfiles
        .account_150k()
    )

    assert profile.account_size == 150000
    assert profile.profit_target == 9000.0
    assert profile.maximum_loss_limit == 4500.0
    assert profile.max_mini_contracts == 15
    assert profile.max_micro_contracts == 150


def test_registry_contains_topstep():

    registry = (
        AccountRegistryV1()
    )

    assert (
        "TOPSTEP_50K"
        in registry.list_accounts()
    )

    assert (
        "TOPSTEP_150K"
        in registry.list_accounts()
    )


def test_topstep_50k_nq_limit():

    validator = build_validator(
        "TOPSTEP_50K"
    )

    approved = validator.validate_trade(
        symbol="NQ",
        contracts=5,
        risk_amount=100.0,
    )

    blocked = validator.validate_trade(
        symbol="NQ",
        contracts=6,
        risk_amount=100.0,
    )

    assert approved["status"] == "APPROVED"

    assert blocked["status"] == "BLOCKED"

    assert (
        blocked["reason"]
        == "MAX_CONTRACTS_EXCEEDED"
    )

    assert blocked["allowed_contracts"] == 5


def test_topstep_50k_mnq_limit():

    validator = build_validator(
        "TOPSTEP_50K"
    )

    approved = validator.validate_trade(
        symbol="MNQ",
        contracts=50,
        risk_amount=100.0,
    )

    blocked = validator.validate_trade(
        symbol="MNQ",
        contracts=51,
        risk_amount=100.0,
    )

    assert approved["status"] == "APPROVED"

    assert blocked["status"] == "BLOCKED"

    assert blocked["allowed_contracts"] == 50


def test_topstep_150k_nq_limit():

    validator = build_validator(
        "TOPSTEP_150K"
    )

    approved = validator.validate_trade(
        symbol="NQ",
        contracts=15,
        risk_amount=100.0,
    )

    blocked = validator.validate_trade(
        symbol="NQ",
        contracts=16,
        risk_amount=100.0,
    )

    assert approved["status"] == "APPROVED"

    assert blocked["status"] == "BLOCKED"

    assert blocked["allowed_contracts"] == 15


def test_topstep_150k_mnq_limit():

    validator = build_validator(
        "TOPSTEP_150K"
    )

    approved = validator.validate_trade(
        symbol="MNQ",
        contracts=150,
        risk_amount=100.0,
    )

    blocked = validator.validate_trade(
        symbol="MNQ",
        contracts=151,
        risk_amount=100.0,
    )

    assert approved["status"] == "APPROVED"

    assert blocked["status"] == "BLOCKED"

    assert blocked["allowed_contracts"] == 150
