from backend.accounts.account_registry_v1 import (
    AccountRegistryV1,
)

from backend.accounts.profiles.takeprofit_profiles import (
    TakeProfitTraderProfiles,
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


def test_tpt_50k_profile():

    profile = (
        TakeProfitTraderProfiles
        .account_50k()
    )

    assert profile.account_size == 50000
    assert profile.profit_target == 3000
    assert profile.max_drawdown == 2000
    assert profile.max_mini_contracts == 6
    assert profile.max_micro_contracts == 60
    assert profile.maximum_loss_limit == 2000.0
    assert profile.account_stage == "EVALUATION"


def test_tpt_150k_profile():

    profile = (
        TakeProfitTraderProfiles
        .account_150k()
    )

    assert profile.account_size == 150000
    assert profile.profit_target == 9000
    assert profile.max_drawdown == 4500
    assert profile.max_mini_contracts == 15
    assert profile.max_micro_contracts == 150
    assert profile.maximum_loss_limit == 4500.0
    assert profile.account_stage == "EVALUATION"


def test_registry_contains_tpt():

    registry = AccountRegistryV1()

    accounts = registry.list_accounts()

    assert (
        "TAKE_PROFIT_TRADER_50K"
        in accounts
    )

    assert (
        "TAKE_PROFIT_TRADER_150K"
        in accounts
    )


def test_tpt_50k_nq_boundary():

    validator = build_validator(
        "TAKE_PROFIT_TRADER_50K"
    )

    approved = validator.validate_trade(
        symbol="NQ",
        contracts=6,
        risk_amount=100.0,
    )

    blocked = validator.validate_trade(
        symbol="NQ",
        contracts=7,
        risk_amount=100.0,
    )

    assert approved["status"] == "APPROVED"

    assert blocked["status"] == "BLOCKED"

    assert (
        blocked["reason"]
        == "MAX_CONTRACTS_EXCEEDED"
    )

    assert blocked["allowed_contracts"] == 6


def test_tpt_50k_mnq_boundary():

    validator = build_validator(
        "TAKE_PROFIT_TRADER_50K"
    )

    approved = validator.validate_trade(
        symbol="MNQ",
        contracts=60,
        risk_amount=100.0,
    )

    blocked = validator.validate_trade(
        symbol="MNQ",
        contracts=61,
        risk_amount=100.0,
    )

    assert approved["status"] == "APPROVED"

    assert blocked["status"] == "BLOCKED"

    assert blocked["allowed_contracts"] == 60


def test_tpt_150k_nq_boundary():

    validator = build_validator(
        "TAKE_PROFIT_TRADER_150K"
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


def test_tpt_150k_mnq_boundary():

    validator = build_validator(
        "TAKE_PROFIT_TRADER_150K"
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
