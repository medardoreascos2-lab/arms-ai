from enum import Enum
from types import SimpleNamespace


from backend.execution.execution_position_bridge_v1 import (
    ExecutionPositionBridgeV1,
)


class FakeAction(Enum):

    BUY = "BUY"

    SELL = "SELL"

    HOLD = "HOLD"


class FakeLifecycle:

    def __init__(self):

        self.calls = []


    def open_position(
        self,
        *,
        direction,
        entry_price,
        stop_loss,
        take_profit,
    ):

        self.calls.append(
            {
                "direction":
                    direction,

                "entry_price":
                    entry_price,

                "stop_loss":
                    stop_loss,

                "take_profit":
                    take_profit,
            }
        )


class FakeApprovedRiskGate:

    def __init__(self):

        self.calls = []


    def evaluate_trade(
        self,
        *,
        symbol,
        side,
        contracts,
        risk_amount,
    ):

        self.calls.append(
            {
                "symbol":
                    symbol,

                "side":
                    side,

                "contracts":
                    contracts,

                "risk_amount":
                    risk_amount,
            }
        )

        return {
            "execution":
                "APPROVED",

            "account":
                "TEST_50K",
        }


class FakeBlockedRiskGate:

    def __init__(
        self,
        reason="RISK_LIMIT_EXCEEDED",
    ):

        self.reason = reason

        self.calls = []


    def evaluate_trade(
        self,
        *,
        symbol,
        side,
        contracts,
        risk_amount,
    ):

        self.calls.append(
            {
                "symbol":
                    symbol,

                "side":
                    side,

                "contracts":
                    contracts,

                "risk_amount":
                    risk_amount,
            }
        )

        return {
            "execution":
                "BLOCKED",

            "reason":
                self.reason,
        }


def build_decision(
    action,
):

    return SimpleNamespace(
        action=action,
        metadata={
            "stop_loss":
                19950.0,

            "take_profit":
                20200.0,
        },
    )


def test_buy_opens_long_after_risk_approval():

    lifecycle = FakeLifecycle()

    risk_gate = (
        FakeApprovedRiskGate()
    )

    bridge = (
        ExecutionPositionBridgeV1(
            lifecycle=lifecycle,
            risk_gate=risk_gate,
        )
    )


    result = bridge.execute(
        decision=build_decision(
            FakeAction.BUY
        ),
        price=20000.0,
        symbol="MNQ",
        contracts=2,
        risk_amount=100.0,
    )


    assert result.executed is True

    assert (
        result.reason
        == "LONG OPENED"
    )

    assert len(
        risk_gate.calls
    ) == 1

    assert len(
        lifecycle.calls
    ) == 1

    assert (
        lifecycle.calls[0][
            "direction"
        ]
        == "LONG"
    )


def test_sell_opens_short_after_risk_approval():

    lifecycle = FakeLifecycle()

    bridge = (
        ExecutionPositionBridgeV1(
            lifecycle=lifecycle,
            risk_gate=(
                FakeApprovedRiskGate()
            ),
        )
    )


    result = bridge.execute(
        decision=build_decision(
            FakeAction.SELL
        ),
        price=20000.0,
        symbol="MNQ",
        contracts=1,
        risk_amount=75.0,
    )


    assert result.executed is True

    assert (
        result.reason
        == "SHORT OPENED"
    )

    assert len(
        lifecycle.calls
    ) == 1

    assert (
        lifecycle.calls[0][
            "direction"
        ]
        == "SHORT"
    )


def test_blocked_trade_never_opens_position():

    lifecycle = FakeLifecycle()

    risk_gate = (
        FakeBlockedRiskGate(
            "MAX_CONTRACTS_EXCEEDED"
        )
    )

    bridge = (
        ExecutionPositionBridgeV1(
            lifecycle=lifecycle,
            risk_gate=risk_gate,
        )
    )


    result = bridge.execute(
        decision=build_decision(
            FakeAction.BUY
        ),
        price=20000.0,
        symbol="NQ",
        contracts=50,
        risk_amount=500.0,
    )


    assert result.executed is False

    assert (
        result.reason
        == "MAX_CONTRACTS_EXCEEDED"
    )

    assert len(
        risk_gate.calls
    ) == 1

    assert (
        lifecycle.calls
        == []
    )


def test_hold_does_not_call_risk_gate():

    lifecycle = FakeLifecycle()

    risk_gate = (
        FakeApprovedRiskGate()
    )

    bridge = (
        ExecutionPositionBridgeV1(
            lifecycle=lifecycle,
            risk_gate=risk_gate,
        )
    )


    result = bridge.execute(
        decision=build_decision(
            FakeAction.HOLD
        ),
        price=20000.0,
        symbol="MNQ",
        contracts=1,
        risk_amount=50.0,
    )


    assert result.executed is False

    assert (
        result.reason
        == "NO EXECUTION"
    )

    assert (
        risk_gate.calls
        == []
    )

    assert (
        lifecycle.calls
        == []
    )


def test_missing_stop_loss_is_rejected_before_risk():

    lifecycle = FakeLifecycle()

    risk_gate = (
        FakeApprovedRiskGate()
    )

    bridge = (
        ExecutionPositionBridgeV1(
            lifecycle=lifecycle,
            risk_gate=risk_gate,
        )
    )

    decision = SimpleNamespace(
        action=FakeAction.BUY,
        metadata={
            "take_profit":
                20200.0,
        },
    )


    try:

        bridge.execute(
            decision=decision,
            price=20000.0,
            symbol="MNQ",
            contracts=1,
            risk_amount=50.0,
        )

    except ValueError as exc:

        assert (
            "stop_loss"
            in str(exc)
        )

    else:

        raise AssertionError(
            "Se esperaba ValueError."
        )


    assert risk_gate.calls == []

    assert lifecycle.calls == []
