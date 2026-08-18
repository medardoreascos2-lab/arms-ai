from backend.execution.execution_risk_gate_v1 import (
    ExecutionRiskGateV1,
)

from backend.risk.risk_event_logger_v1 import (
    RiskEventLoggerV1,
)


class FakeApprovedValidator:

    def validate_trade(
        self,
        contracts: int,
        risk_amount: float,
        symbol: str | None = None,
    ):

        return {
            "status":
                "APPROVED",

            "account":
                "TEST_50K",

            "account_size":
                50000,

            "risk_used":
                risk_amount,

            "contracts":
                contracts,
        }


class FakeBlockedValidator:

    def __init__(
        self,
        reason: str,
    ):

        self.reason = reason


    def validate_trade(
        self,
        contracts: int,
        risk_amount: float,
        symbol: str | None = None,
    ):

        return {
            "status":
                "BLOCKED",

            "reason":
                self.reason,
        }


def test_approved_trade_is_logged():

    logger = (
        RiskEventLoggerV1()
    )

    gate = (
        ExecutionRiskGateV1(
            validator=(
                FakeApprovedValidator()
            ),
            logger=logger,
        )
    )


    result = (
        gate.evaluate_trade(
            symbol="mnq",
            side="buy",
            contracts=2,
            risk_amount=150.0,
        )
    )


    assert (
        result["execution"]
        == "APPROVED"
    )

    assert (
        result["symbol"]
        == "MNQ"
    )

    assert (
        result["side"]
        == "BUY"
    )

    assert (
        result["account"]
        == "TEST_50K"
    )


    events = (
        gate.get_risk_events()
    )


    assert len(events) == 1

    assert (
        events[0]["status"]
        == "APPROVED"
    )

    assert (
        events[0]["account"]
        == "TEST_50K"
    )


def test_max_contracts_block_is_logged():

    logger = (
        RiskEventLoggerV1()
    )

    gate = (
        ExecutionRiskGateV1(
            validator=(
                FakeBlockedValidator(
                    "MAX_CONTRACTS_EXCEEDED"
                )
            ),
            logger=logger,
        )
    )


    result = (
        gate.evaluate_trade(
            symbol="NQ",
            side="BUY",
            contracts=10,
            risk_amount=200.0,
        )
    )


    assert (
        result["execution"]
        == "BLOCKED"
    )

    assert (
        result["reason"]
        == "MAX_CONTRACTS_EXCEEDED"
    )


    events = (
        gate.get_risk_events()
    )


    assert len(events) == 1

    assert (
        events[0]["status"]
        == "BLOCKED"
    )

    assert (
        events[0]["reason"]
        == "MAX_CONTRACTS_EXCEEDED"
    )


def test_risk_limit_block_is_logged():

    gate = (
        ExecutionRiskGateV1(
            validator=(
                FakeBlockedValidator(
                    "RISK_LIMIT_EXCEEDED"
                )
            ),
            logger=(
                RiskEventLoggerV1()
            ),
        )
    )


    result = (
        gate.evaluate_trade(
            symbol="MNQ",
            side="SELL",
            contracts=1,
            risk_amount=500.0,
        )
    )


    assert (
        result["execution"]
        == "BLOCKED"
    )

    assert (
        result["reason"]
        == "RISK_LIMIT_EXCEEDED"
    )


def test_invalid_side_is_rejected():

    gate = (
        ExecutionRiskGateV1(
            validator=(
                FakeApprovedValidator()
            ),
            logger=(
                RiskEventLoggerV1()
            ),
        )
    )


    try:

        gate.evaluate_trade(
            symbol="MNQ",
            side="HOLD",
            contracts=1,
            risk_amount=100.0,
        )

    except ValueError as exc:

        assert (
            "BUY o SELL"
            in str(exc)
        )

    else:

        raise AssertionError(
            "Se esperaba ValueError."
        )


def test_zero_contracts_are_rejected():

    gate = (
        ExecutionRiskGateV1(
            validator=(
                FakeApprovedValidator()
            ),
            logger=(
                RiskEventLoggerV1()
            ),
        )
    )


    try:

        gate.evaluate_trade(
            symbol="MNQ",
            side="BUY",
            contracts=0,
            risk_amount=100.0,
        )

    except ValueError as exc:

        assert (
            "mayor que cero"
            in str(exc)
        )

    else:

        raise AssertionError(
            "Se esperaba ValueError."
        )
