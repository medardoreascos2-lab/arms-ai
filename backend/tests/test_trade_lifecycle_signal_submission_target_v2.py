from backend.services.signal_submission_target_v2 import (
    SignalSubmissionTargetV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


def test_trade_lifecycle_service_implements_submission_target():

    assert issubclass(
        TradeLifecycleServiceV2,
        SignalSubmissionTargetV2,
    )


def test_submit_signal_is_concrete():

    assert (
        TradeLifecycleServiceV2.submit_signal
        is not SignalSubmissionTargetV2.submit_signal
    )
