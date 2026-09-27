from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(
        encoding="utf-8"
    )


def test_bridge_requires_activation_directory():
    text = source()

    assert "ActivationDirectory" in text
    assert "[NinjaScriptProperty]" in text


def test_activation_file_is_command_scoped():
    text = source()

    assert (
        'CommandId.Trim() + ".arm.json"'
        in text
    )


def test_activation_requires_exact_command_identity():
    text = source()

    assert '"command_id"' in text

    assert (
        "Activation command identity mismatch."
        in text
    )


def test_activation_requires_explicit_permit():
    text = source()

    assert '"permit"' in text

    assert (
        "ONE_SHOT_SIM101_V2"
        in text
    )

    assert (
        "Activation permit is invalid."
        in text
    )


def test_activation_requires_sim101_target():
    text = source()

    assert '"account"' in text

    assert (
        '"Sim101"'
        in text
    )

    assert (
        "Activation account is invalid."
        in text
    )


def test_activation_is_read_only():
    text = source()

    assert "ReadActivationEvidence(" in text

    forbidden = (
        "DeleteActivation",
        "File.Delete(",
        "File.Move(",
        "File.Replace(",
    )

    for token in forbidden:
        assert token not in text


def test_activation_is_checked_before_create_order():
    text = source()

    activation_index = text.index(
        "ReadActivationEvidence("
    )

    create_index = text.index(
        "selectedAccount.CreateOrder("
    )

    assert activation_index < create_index


def test_hard_disable_remains_false_for_r48t7():
    text = source()

    assert (
        "NATIVE_SUBMIT_ENABLED = false"
        in text
    )
