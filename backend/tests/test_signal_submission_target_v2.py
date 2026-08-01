import pytest

from backend.services.signal_submission_target_v2 import (
    SignalSubmissionTargetV2,
)


class FakeSignalSubmissionTargetV2(
    SignalSubmissionTargetV2,
):

    def __init__(self):
        self.calls = []

    def submit_signal(
        self,
        *,
        signal,
        order_type,
        risk_context=None,
        order_context=None,
    ):
        call = {
            "signal": signal,
            "order_type": order_type,
            "risk_context": risk_context,
            "order_context": order_context,
        }

        self.calls.append(call)

        return {
            "accepted": True,
            "call": call,
        }


def build_signal():
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 20000.0,
        "stop_loss": 19950.0,
        "take_profit": 20100.0,
        "contracts": 2,
    }


def test_base_target_cannot_be_instantiated():

    with pytest.raises(TypeError):
        SignalSubmissionTargetV2()


def test_concrete_target_submits_signal():

    target = FakeSignalSubmissionTargetV2()

    signal = build_signal()

    result = target.submit_signal(
        signal=signal,
        order_type="MARKET",
    )

    assert result["accepted"] is True
    assert len(target.calls) == 1

    assert target.calls[0]["signal"] is signal
    assert target.calls[0]["order_type"] == "MARKET"
    assert target.calls[0]["risk_context"] is None
    assert target.calls[0]["order_context"] is None


def test_concrete_target_accepts_optional_contexts():

    target = FakeSignalSubmissionTargetV2()

    risk_context = {
        "account_balance": 17000.0,
        "risk_percent": 0.5,
    }

    order_context = {
        "session": "NEW_YORK",
    }

    target.submit_signal(
        signal=build_signal(),
        order_type="LIMIT",
        risk_context=risk_context,
        order_context=order_context,
    )

    call = target.calls[0]

    assert call["risk_context"] is risk_context
    assert call["order_context"] is order_context


def test_subclass_without_submit_signal_is_abstract():

    class InvalidTarget(
        SignalSubmissionTargetV2,
    ):
        pass

    with pytest.raises(TypeError):
        InvalidTarget()
