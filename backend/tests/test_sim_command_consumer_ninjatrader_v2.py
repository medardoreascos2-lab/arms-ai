from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimCommandConsumerV2.cs"
)


def source():
    return SOURCE.read_text(
        encoding="utf-8"
    )


def test_native_consumer_source_exists():
    assert SOURCE.is_file()


def test_consumer_has_expected_ninjascript_identity():
    text = source()

    assert (
        "class ArmsSimCommandConsumerV2"
        in text
    )

    assert ": Indicator" in text


def test_consumer_exposes_command_directory():
    text = source()

    assert "CommandDirectory" in text
    assert "[NinjaScriptProperty]" in text


def test_consumer_requires_selected_sim_account():
    text = source()

    assert "SelectedAccountName" in text

    assert (
        "Provider.Simulator"
        in text
    )


def test_consumer_is_explicitly_non_executable():
    text = source()

    assert (
        'SIM_EXECUTION_AUTHORITY = "DISABLED"'
        in text
    )

    assert (
        'EXTERNAL_ORDER_AUTHORITY = false'
        in text
    )


def test_consumer_emits_validation_only_diagnostic():
    text = source()

    assert (
        "VALIDATED_NO_EXECUTION"
        in text
    )


def test_consumer_does_not_emit_native_acknowledged_status():
    text = source()

    assert (
        '"ACKNOWLEDGED"'
        not in text
    )


def test_consumer_has_no_native_order_creation_or_submission_surface():
    text = source()

    forbidden = (
        "CreateOrder(",
        ".CreateOrder(",
        "Submit(",
        ".Submit(",
        "SubmitOrder",
        "SubmitOrderUnmanaged",
        "EnterLong(",
        "EnterShort(",
        "SetStopLoss(",
        "SetProfitTarget(",
        "ChangeOrder(",
        "CancelOrder(",
        "Flatten(",
    )

    for token in forbidden:
        assert token not in text


def test_consumer_has_no_mutation_commands():
    text = source()

    forbidden = (
        "MODIFY_ORDER",
        "CANCEL_ORDER",
        "CLOSE_POSITION",
        "CLOSE_PARTIAL",
    )

    for token in forbidden:
        assert token not in text


def test_consumer_only_recognizes_submit_command_for_validation():
    text = source()

    assert (
        '"SUBMIT_ORDER"'
        in text
    )


def test_consumer_never_claims_fill_or_position_evidence():
    text = source()

    forbidden = (
        '"fill_id"',
        '"filled_price"',
        '"position_id"',
        '"broker_position_id"',
    )

    for token in forbidden:
        assert token not in text
