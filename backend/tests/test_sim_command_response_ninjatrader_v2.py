from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimCommandConsumerV2.cs"
)


def source():
    return SOURCE.read_text(
        encoding="utf-8"
    )


def test_response_directory_property_exists():
    text = source()

    assert "ResponseDirectory" in text
    assert "[NinjaScriptProperty]" in text


def test_validation_response_status_is_non_executable():
    text = source()

    assert (
        '"VALIDATED_NO_EXECUTION"'
        in text
    )

    forbidden = (
        '"ACKNOWLEDGED"',
        '"REJECTED"',
        '"FILLED"',
        '"PARTIALLY_FILLED"',
        '"WORKING"',
    )

    for token in forbidden:
        assert token not in text


def test_response_contains_command_identity_only():
    text = source()

    required = (
        '"command_id"',
        '"operation_id"',
        '"client_order_id"',
        '"status"',
        '"sim_execution_authority"',
        '"external_order_authority"',
    )

    for token in required:
        assert token in text


def test_response_never_contains_execution_evidence():
    text = source()

    forbidden = (
        '"order_id"',
        '"fill_id"',
        '"filled_price"',
        '"position_id"',
        '"broker_position_id"',
        '"accepted"',
    )

    for token in forbidden:
        assert token not in text


def test_response_uses_create_new_semantics():
    text = source()

    assert "FileMode.CreateNew" in text

    assert (
        "response evidence collision"
        in text
    )


def test_response_file_is_separate_from_command_file():
    text = source()

    assert "ResponseDirectory" in text
    assert "CommandDirectory" in text

    assert (
        'Path.Combine('
        in text
    )


def test_response_is_flushed_to_disk():
    text = source()

    assert ".Flush(true)" in text


def test_existing_identical_response_is_idempotent():
    text = source()

    assert (
        "idempotent response evidence"
        in text
    )


def test_consumer_still_has_no_order_submission_surface():
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
        "ChangeOrder(",
        "CancelOrder(",
        "Flatten(",
    )

    for token in forbidden:
        assert token not in text
