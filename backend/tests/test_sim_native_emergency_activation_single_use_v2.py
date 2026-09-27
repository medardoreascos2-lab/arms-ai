from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(encoding="utf-8")


def test_activation_requires_created_utc():
    text = source()

    assert '"created_utc"' in text


def test_activation_requires_nonce():
    text = source()

    assert '"nonce"' in text


def test_activation_has_maximum_age():
    text = source()

    assert "EMERGENCY_ACTIVATION_MAX_AGE_SECONDS" in text


def test_activation_rejects_future_timestamp():
    text = source()

    assert (
        "Emergency activation timestamp is in the future."
        in text
    )


def test_activation_rejects_expired_timestamp():
    text = source()

    assert (
        "Emergency activation evidence expired."
        in text
    )


def test_activation_has_consumed_marker():
    text = source()

    assert ".consumed" in text


def test_activation_rejects_already_consumed():
    text = source()

    assert (
        "Emergency activation evidence was already consumed."
        in text
    )


def test_consumed_marker_is_created_before_native_mutation():
    text = source()

    consume_index = text.index(
        "ConsumeEmergencyFlattenActivation("
    )

    hard_stop = text.index(
        "if (!NATIVE_EMERGENCY_FLATTEN_ENABLED)"
    )

    assert consume_index < hard_stop


def test_entry_remains_disabled_while_emergency_is_enabled():
    text = source()

    assert "NATIVE_SUBMIT_ENABLED = false" in text

    assert (
        "NATIVE_EMERGENCY_FLATTEN_ENABLED = true"
        in text
    )
