from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(
        encoding="utf-8"
    )


def test_bridge_has_flat_preflight():
    text = source()

    assert "ValidateFlatPreflight(" in text


def test_preflight_inspects_native_positions():
    text = source()

    assert "selectedAccount.Positions" in text
    assert ".MarketPosition" in text
    assert "MarketPosition.Flat" in text


def test_non_flat_position_blocks_submit():
    text = source()

    assert (
        "Target instrument is not flat."
        in text
    )


def test_preflight_inspects_native_orders():
    text = source()

    assert "selectedAccount.Orders" in text
    assert ".OrderState" in text


def test_only_terminal_order_states_are_ignored():
    text = source()

    for state in (
        "OrderState.Cancelled",
        "OrderState.Filled",
        "OrderState.Rejected",
    ):
        assert state in text


def test_non_terminal_order_blocks_submit():
    text = source()

    assert (
        "Target instrument has active native order."
        in text
    )


def test_preflight_is_target_instrument_scoped():
    text = source()

    assert (
        "ReferenceEquals("
        in text
    )

    assert (
        "position.Instrument"
        in text
    )

    assert (
        "order.Instrument"
        in text
    )


def test_instrument_is_resolved_before_preflight():
    text = source()

    instrument_index = text.index(
        "NinjaTrader.Cbi.Instrument.GetInstrument("
    )

    preflight_index = text.index(
        "ValidateFlatPreflight("
    )

    assert instrument_index < preflight_index


def test_preflight_happens_before_create_order():
    text = source()

    preflight_index = text.index(
        "ValidateFlatPreflight("
    )

    create_index = text.index(
        "selectedAccount.CreateOrder("
    )

    assert preflight_index < create_index


def test_hard_disable_remains_false():
    text = source()

    assert (
        "NATIVE_SUBMIT_ENABLED = false"
        in text
    )


def test_auto_retry_remains_forbidden():
    text = source()

    assert (
        "AUTO_RETRY_ALLOWED = false"
        in text
    )
