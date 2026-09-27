from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(
        encoding="utf-8"
    )


def test_bridge_has_native_evidence_directory():
    text = source()

    assert "NativeEvidenceDirectory" in text
    assert "[NinjaScriptProperty]" in text


def test_order_update_writes_durable_evidence():
    text = source()

    assert "WriteOrderEvidence(" in text

    required = (
        "ORDER_UPDATE",
        r'\"order_id\"',
        r'\"order_state\"',
        r'\"quantity\"',
        r'\"filled\"',
        r'\"average_fill_price\"',
    )

    for token in required:
        assert token in text


def test_execution_update_writes_durable_evidence():
    text = source()

    assert "WriteExecutionEvidence(" in text

    required = (
        "EXECUTION_UPDATE",
        r'\"execution_id\"',
        r'\"order_id\"',
        r'\"quantity\"',
        r'\"price\"',
    )

    for token in required:
        assert token in text


def test_native_evidence_is_create_once():
    text = source()

    assert "FileMode.CreateNew" in text

    assert (
        "native evidence collision"
        in text
    )


def test_native_evidence_is_synced_before_success():
    text = source()

    assert ".Flush(true)" in text


def test_native_evidence_keeps_command_identity():
    text = source()

    assert '"command_id"' in text
    assert '"operation_id"' in text
    assert '"client_order_id"' in text


def test_submit_still_remains_hard_disabled():
    text = source()

    assert (
        "NATIVE_SUBMIT_ENABLED = false"
        in text
    )


def test_auto_retry_still_forbidden():
    text = source()

    assert (
        "AUTO_RETRY_ALLOWED = false"
        in text
    )
