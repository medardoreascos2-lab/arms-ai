from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(
        encoding="utf-8"
    )


def test_bridge_requires_command_directory():
    text = source()

    assert "CommandDirectory" in text
    assert "[NinjaScriptProperty]" in text


def test_bridge_requires_validation_response_directory():
    text = source()

    assert "ValidationResponseDirectory" in text


def test_bridge_loads_durable_command_by_command_id():
    text = source()

    assert (
        'CommandId.Trim() + ".json"'
        in text
    )

    assert (
        "FileMode.Open"
        in text
    )

    assert (
        "FileAccess.Read"
        in text
    )


def test_bridge_requires_durable_operation_identity():
    text = source()

    assert '"operation_id"' in text
    assert '"client_order_id"' in text

    assert (
        "operationId != clientOrderId"
        in text
    )

    assert (
        "Durable command identity mismatch."
        in text
    )


def test_bridge_requires_validation_response():
    text = source()

    assert (
        "VALIDATED_NO_EXECUTION"
        in text
    )

    assert (
        "Validation response is required."
        in text
    )


def test_bridge_requires_validation_response_identity_match():
    text = source()

    assert (
        "Validation response identity mismatch."
        in text
    )


def test_bridge_rejects_validation_that_claims_execution_authority():
    text = source()

    assert (
        '"sim_execution_authority"'
        in text
    )

    assert (
        '"external_order_authority"'
        in text
    )

    assert (
        "Validation response authority is invalid."
        in text
    )


def test_bridge_execution_fields_are_derived_from_command_payload():
    text = source()

    required = (
        '"symbol"',
        '"side"',
        '"quantity"',
    )

    for token in required:
        assert token in text

    assert (
        "ReadSubmitCommand("
        in text
    )


def test_bridge_still_limits_one_contract_and_market():
    text = source()

    assert "quantity != 1" in text
    assert 'orderType != "MARKET"' in text


def test_hard_disable_remains_false():
    text = source()

    assert (
        "NATIVE_SUBMIT_ENABLED = false"
        in text
    )


def test_no_auto_retry_remains_false():
    text = source()

    assert (
        "AUTO_RETRY_ALLOWED = false"
        in text
    )
