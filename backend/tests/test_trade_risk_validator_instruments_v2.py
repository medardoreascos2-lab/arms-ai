from backend.risk.trade_risk_validator_v2 import (
    TradeRiskValidatorV2,
)


class FakeRiskEngine:

    def get_active_risk_profile(
        self,
    ):

        return {
            "account":
                "TEST_ACCOUNT",
            "account_size":
                50000,
            "risk_per_trade":
                250.0,
            "max_contracts":
                5,
            "max_mini_contracts":
                5,
            "max_micro_contracts":
                50,
        }


def build_validator():

    return TradeRiskValidatorV2(
        risk_engine=FakeRiskEngine()
    )


def test_nq_uses_mini_contract_limit():

    validator = build_validator()

    result = validator.validate_trade(
        symbol="NQ",
        contracts=5,
        risk_amount=200.0,
    )

    assert result["status"] == "APPROVED"
    assert result["symbol"] == "NQ"
    assert result["contract_class"] == "MINI"
    assert result["allowed_contracts"] == 5
    assert result["point_value"] == 20.0
    assert result["tick_value"] == 5.0


def test_nq_blocks_above_mini_limit():

    validator = build_validator()

    result = validator.validate_trade(
        symbol="NQ",
        contracts=6,
        risk_amount=200.0,
    )

    assert result["status"] == "BLOCKED"
    assert (
        result["reason"]
        == "MAX_CONTRACTS_EXCEEDED"
    )
    assert result["allowed_contracts"] == 5


def test_mnq_uses_micro_contract_limit():

    validator = build_validator()

    result = validator.validate_trade(
        symbol="MNQ",
        contracts=50,
        risk_amount=200.0,
    )

    assert result["status"] == "APPROVED"
    assert result["symbol"] == "MNQ"
    assert result["contract_class"] == "MICRO"
    assert result["allowed_contracts"] == 50
    assert result["point_value"] == 2.0
    assert result["tick_value"] == 0.5


def test_mnq_blocks_above_micro_limit():

    validator = build_validator()

    result = validator.validate_trade(
        symbol="MNQ",
        contracts=51,
        risk_amount=200.0,
    )

    assert result["status"] == "BLOCKED"
    assert (
        result["reason"]
        == "MAX_CONTRACTS_EXCEEDED"
    )
    assert result["allowed_contracts"] == 50


def test_risk_amount_still_blocks_micro():

    validator = build_validator()

    result = validator.validate_trade(
        symbol="MNQ",
        contracts=1,
        risk_amount=251.0,
    )

    assert result["status"] == "BLOCKED"
    assert (
        result["reason"]
        == "RISK_LIMIT_EXCEEDED"
    )
    assert result["allowed_risk"] == 250.0


def test_symbol_is_normalized():

    validator = build_validator()

    result = validator.validate_trade(
        symbol=" mnq ",
        contracts=1,
        risk_amount=100.0,
    )

    assert result["status"] == "APPROVED"
    assert result["symbol"] == "MNQ"
    assert result["contract_class"] == "MICRO"
