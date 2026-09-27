from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(
        encoding="utf-8"
    )


def test_native_submit_bridge_source_exists():
    assert SOURCE.is_file()


def test_bridge_is_ninjascript_indicator():
    text = source()

    assert (
        "class ArmsSimNativeSubmitBridgeV2"
        in text
    )

    assert ": Indicator" in text


def test_bridge_is_explicitly_execution_disabled():
    text = source()

    assert (
        'SIM_EXECUTION_AUTHORITY = "DISABLED"'
        in text
    )

    assert (
        "EXTERNAL_ORDER_AUTHORITY = false"
        in text
    )

    assert (
        "NATIVE_SUBMIT_ENABLED = false"
        in text
    )


def test_bridge_requires_selected_simulator_account():
    text = source()

    assert "SelectedAccountName" in text

    assert text.count(
        "Provider.Simulator"
    ) >= 2


def test_bridge_subscribes_native_order_updates():
    text = source()

    assert (
        "selectedAccount.OrderUpdate +="
        in text
    )

    assert (
        "selectedAccount.OrderUpdate -="
        in text
    )

    assert (
        "OrderEventArgs"
        in text
    )


def test_bridge_subscribes_native_execution_updates():
    text = source()

    assert (
        "selectedAccount.ExecutionUpdate +="
        in text
    )

    assert (
        "selectedAccount.ExecutionUpdate -="
        in text
    )

    assert (
        "ExecutionEventArgs"
        in text
    )


def test_order_observer_reads_native_order_identity():
    text = source()

    required = (
        ".OrderId",
        ".OrderState",
        ".Quantity",
        ".Filled",
        ".AverageFillPrice",
    )

    for token in required:
        assert token in text


def test_execution_observer_reads_native_fill_identity():
    text = source()

    required = (
        ".ExecutionId",
        ".Quantity",
        ".Price",
        ".Order",
    )

    for token in required:
        assert token in text


def test_bridge_reports_order_update_without_claiming_fill():
    text = source()

    assert (
        "ARMS_SIM_NATIVE_ORDER_UPDATE"
        in text
    )

    assert (
        "ARMS_SIM_NATIVE_EXECUTION_UPDATE"
        in text
    )


def test_bridge_submit_path_exists_but_remains_hard_disabled():
    text = source()

    assert (
        "NATIVE_SUBMIT_ENABLED = false"
        in text
    )

    assert (
        "selectedAccount.CreateOrder("
        in text
    )

    assert (
        "selectedAccount.Submit("
        in text
    )

    assert (
        "if (!NATIVE_SUBMIT_ENABLED)"
        in text
    )


def test_bridge_has_guarded_emergency_cancel_flatten_surface():
    text = source()

    assert ".Change(" not in text
    assert "CancelOrder(" not in text
    assert "ChangeOrder(" not in text

    assert "selectedAccount.Cancel(" in text
    assert "selectedAccount.Flatten(" in text

    assert (
        "NATIVE_EMERGENCY_FLATTEN_ENABLED = true"
        in text
    )

    assert "NATIVE_SUBMIT_ENABLED = false" in text

    gate = text.index(
        "if (!NATIVE_EMERGENCY_FLATTEN_ENABLED)"
    )

    cancel_call = text.index(
        "selectedAccount.Cancel("
    )

    flatten_call = text.index(
        "selectedAccount.Flatten("
    )

    assert gate < cancel_call
    assert gate < flatten_call


def test_bridge_never_auto_rebinds_account():
    text = source()

    assert (
        "selectedAccount = ResolveSelectedAccount();"
        in text
    )

    assert (
        "ValidateSelectedAccount();"
        in text
    )

    assert text.count(
        "ResolveSelectedAccount()"
    ) == 2
