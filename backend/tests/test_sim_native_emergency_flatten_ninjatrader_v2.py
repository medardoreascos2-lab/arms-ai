from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(encoding="utf-8")


def test_emergency_flatten_has_separate_enablement_switch():
    text = source()

    assert (
        "NATIVE_EMERGENCY_FLATTEN_ENABLED = true"
        in text
    )

    assert "NATIVE_SUBMIT_ENABLED = false" in text


def test_emergency_flatten_has_separate_arm_token():
    text = source()

    assert "EMERGENCY_FLATTEN_ARM_TOKEN" in text
    assert '"ARM_SIM_EMERGENCY_FLATTEN_V2"' in text


def test_emergency_flatten_has_one_shot_latch():
    text = source()

    assert "emergencyFlattenAttempted" in text


def test_emergency_flatten_has_explicit_method():
    text = source()

    assert "AttemptEmergencyFlatten(" in text


def test_emergency_flatten_revalidates_selected_account():
    text = source()

    assert "ValidateSelectedAccount();" in text


def test_emergency_flatten_is_sim101_only():
    text = source()

    assert '"Sim101"' in text
    assert "selectedAccount.Provider" in text
    assert "Provider.Simulator" in text


def test_emergency_flatten_resolves_exact_instrument():
    text = source()

    assert (
        "NinjaTrader.Cbi.Instrument.GetInstrument("
        in text
    )


def test_emergency_flatten_inspects_target_positions():
    text = source()

    assert "selectedAccount.Positions" in text
    assert "position.Instrument" in text
    assert "position.MarketPosition" in text
    assert "MarketPosition.Flat" in text


def test_emergency_flatten_inspects_target_orders():
    text = source()

    assert "selectedAccount.Orders" in text
    assert "order.Instrument" in text
    assert "order.OrderState" in text


def test_emergency_flatten_can_cancel_target_orders():
    text = source()

    assert "selectedAccount.Cancel(" in text


def test_emergency_flatten_can_flatten_target_instrument():
    text = source()

    assert "selectedAccount.Flatten(" in text


def test_emergency_flatten_has_no_automatic_retry():
    text = source()

    assert "AUTO_RETRY_ALLOWED = false" in text


def test_flat_position_does_not_require_flatten():
    text = source()

    assert (
        "Target instrument already flat."
        in text
    )


def test_emergency_flatten_hard_stop_precedes_native_flatten():
    text = source()

    hard_stop = text.index(
        "NATIVE_EMERGENCY_FLATTEN_ENABLED"
    )

    flatten_call = text.index(
        "selectedAccount.Flatten("
    )

    assert hard_stop < flatten_call


def test_entry_submit_remains_hard_disabled():
    text = source()

    assert "NATIVE_SUBMIT_ENABLED = false" in text


def test_emergency_flatten_has_independent_request_property():
    text = source()

    assert "RequestEmergencyFlatten" in text


def test_emergency_flatten_has_independent_operator_token_property():
    text = source()

    assert "EmergencyFlattenArmToken" in text


def test_emergency_method_checks_its_own_request():
    text = source()

    assert (
        "if (!RequestEmergencyFlatten)"
        in text
    )


def test_emergency_method_checks_its_own_arm_token():
    text = source()

    assert (
        "EmergencyFlattenArmToken"
        in text
    )

    assert (
        "EMERGENCY_FLATTEN_ARM_TOKEN"
        in text
    )


def test_emergency_latch_is_set_before_native_cancel_or_flatten():
    text = source()

    latch_index = text.index(
        "emergencyFlattenAttempted = true"
    )

    cancel_index = text.index(
        "selectedAccount.Cancel("
    )

    flatten_index = text.index(
        "selectedAccount.Flatten("
    )

    assert latch_index < cancel_index
    assert latch_index < flatten_index


def test_emergency_native_calls_are_behind_hard_disable():
    text = source()

    hard_stop = text.index(
        "if (!NATIVE_EMERGENCY_FLATTEN_ENABLED)"
    )

    cancel_index = text.index(
        "selectedAccount.Cancel("
    )

    flatten_index = text.index(
        "selectedAccount.Flatten("
    )

    assert hard_stop < cancel_index
    assert hard_stop < flatten_index
