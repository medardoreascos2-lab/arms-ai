from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(
        encoding="utf-8"
    )


def test_bridge_has_explicit_arm_property():
    text = source()

    assert "OperatorArmToken" in text
    assert "ARM_SIM_ONE_SHOT_V2" in text


def test_bridge_allows_only_one_contract():
    text = source()

    assert "quantity != 1" in text
    assert "Only quantity 1 is allowed." in text


def test_bridge_allows_market_only():
    text = source()

    assert 'orderType != "MARKET"' in text
    assert "Only MARKET is allowed." in text


def test_bridge_allows_buy_or_sell_only():
    text = source()

    assert '"BUY"' in text
    assert '"SELL"' in text
    assert "Unsupported side." in text


def test_bridge_creates_native_market_order():
    text = source()

    assert "selectedAccount.CreateOrder(" in text

    assert "OrderType.Market" in text

    assert "TimeInForce.Day" in text


def test_bridge_submits_exactly_one_order_collection():
    text = source()

    assert "selectedAccount.Submit(" in text
    assert "new[] { nativeOrder }" in text


def test_bridge_never_treats_submit_as_ack():
    text = source()

    assert "SUBMIT_CALLED_AWAITING_ORDER_UPDATE" in text

    forbidden = (
        "SUBMIT_MEANS_ACK",
        "accepted=true",
        "status=ACKNOWLEDGED",
    )

    for token in forbidden:
        assert token not in text


def test_bridge_requires_simulator_provider_before_submit():
    text = source()

    assert (
        "selectedAccount.Provider != Provider.Simulator"
        in text
    )


def test_bridge_has_one_shot_latch():
    text = source()

    assert "submitAttempted" in text
    assert "one-shot submit already attempted" in text


def test_bridge_does_not_auto_retry():
    text = source()

    assert "AUTO_RETRY_ALLOWED = false" in text


def test_bridge_keeps_enabled_emergency_path_separate_from_submit():
    text = source()

    assert ".Change(" not in text
    assert "CancelOrder(" not in text
    assert "ChangeOrder(" not in text

    assert "selectedAccount.Cancel(" in text
    assert "selectedAccount.Flatten(" in text

    assert (
        "NATIVE_EMERGENCY_FLATTEN_ENABLED = true"
        in text
    )

    assert "NATIVE_SUBMIT_ENABLED = false" in text

    gate = text.index(
        "if (!NATIVE_EMERGENCY_FLATTEN_ENABLED)"
    )

    cancel_call = text.index(
        "selectedAccount.Cancel("
    )

    flatten_call = text.index(
        "selectedAccount.Flatten("
    )

    assert gate < cancel_call
    assert gate < flatten_call
