from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/"
    "ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(
        encoding="utf-8"
    )


def runtime_snapshot_method(text):
    start = text.index(
        "private void WriteRuntimeReadinessSnapshot("
    )

    end = text.index(
        "private ",
        start + 10,
    )

    return text[start:end]


def test_bridge_has_runtime_snapshot_directory_property():
    text = source()

    assert "RuntimeSnapshotDirectory" in text
    assert "[NinjaScriptProperty]" in text


def test_bridge_has_runtime_snapshot_writer():
    text = source()

    assert (
        "private void WriteRuntimeReadinessSnapshot("
        in text
    )


def test_runtime_snapshot_has_exact_identity_fields():
    text = source()
    method = runtime_snapshot_method(text)

    required = (
        '\\"schema\\"',
        '\\"observed_at\\"',
        '\\"account_name\\"',
        '\\"provider\\"',
        '\\"connection_status\\"',
        '\\"instrument\\"',
        '\\"physical_test_readiness\\"',
        '\\"position_state\\"',
        '\\"active_order_count\\"',
        '\\"native_submit_enabled\\"',
        '\\"auto_retry_allowed\\"',
    )

    for token in required:
        assert token in method


def test_runtime_snapshot_is_scoped_to_sim101():
    text = source()
    method = runtime_snapshot_method(text)

    assert '"Sim101"' in method
    assert "Provider.Simulator" in method


def test_runtime_snapshot_reads_native_position_state():
    text = source()
    method = runtime_snapshot_method(text)

    assert "selectedAccount.Positions" in method
    assert "MarketPosition.Flat" in method


def test_runtime_snapshot_reads_native_active_orders():
    text = source()
    method = runtime_snapshot_method(text)

    assert "selectedAccount.Orders" in method

    for state in (
        "OrderState.Cancelled",
        "OrderState.Filled",
        "OrderState.Rejected",
    ):
        assert state in method


def test_runtime_snapshot_uses_existing_readiness_evaluator():
    text = source()
    method = runtime_snapshot_method(text)

    assert (
        "EvaluatePhysicalTestReadiness("
        in method
    )


def test_runtime_snapshot_is_read_only():
    text = source()
    method = runtime_snapshot_method(text)

    forbidden = (
        "selectedAccount.Submit(",
        "selectedAccount.Cancel(",
        "selectedAccount.Flatten(",
        "selectedAccount.CreateOrder(",
        "ConsumeSubmitActivation(",
        "ConsumeEmergencyFlattenActivation(",
    )

    for token in forbidden:
        assert token not in method


def test_runtime_snapshot_written_before_execution_requests():
    text = source()

    snapshot = text.index(
        "WriteRuntimeReadinessSnapshot("
    )

    submit_request = text.index(
        "if (RequestOneShotSubmit)"
    )

    flatten_request = text.index(
        "if (RequestEmergencyFlatten)"
    )

    assert snapshot < submit_request
    assert snapshot < flatten_request


def test_runtime_snapshot_preserves_hard_safety_constants():
    text = source()

    assert (
        "private const bool NATIVE_SUBMIT_ENABLED = false;"
        in text
    )

    assert (
        "private const bool AUTO_RETRY_ALLOWED = false;"
        in text
    )
