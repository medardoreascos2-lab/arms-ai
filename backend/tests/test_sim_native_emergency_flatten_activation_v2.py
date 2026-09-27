from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(encoding="utf-8")


def test_emergency_has_activation_directory_property():
    text = source()

    assert "EmergencyActivationDirectory" in text


def test_emergency_activation_uses_separate_permit():
    text = source()

    assert '"EMERGENCY_FLATTEN_SIM101_V2"' in text


def test_emergency_reads_durable_activation():
    text = source()

    assert "ReadEmergencyFlattenActivation(" in text


def test_activation_is_bound_to_sim101():
    text = source()

    assert '"Sim101"' in text


def test_activation_is_bound_to_exact_instrument():
    text = source()

    assert '"instrument"' in text
    assert "InstrumentName" in text


def test_activation_is_bounded_read_only():
    text = source()

    assert "File.ReadAllText(" in text
    assert "1024 * 1024" in text


def test_activation_is_checked_before_emergency_hard_stop():
    text = source()

    activation_index = text.index(
        "ReadEmergencyFlattenActivation("
    )

    hard_stop_index = text.index(
        "if (!NATIVE_EMERGENCY_FLATTEN_ENABLED)"
    )

    assert activation_index < hard_stop_index


def test_emergency_is_enabled_but_entry_remains_disabled():
    text = source()

    assert (
        "NATIVE_EMERGENCY_FLATTEN_ENABLED = true"
        in text
    )

    assert "NATIVE_SUBMIT_ENABLED = false" in text


def test_entry_still_hard_disabled():
    text = source()

    assert "NATIVE_SUBMIT_ENABLED = false" in text
