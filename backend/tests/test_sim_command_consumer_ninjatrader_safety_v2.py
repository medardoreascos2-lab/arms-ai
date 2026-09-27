from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimCommandConsumerV2.cs"
)


def source():
    return SOURCE.read_text(
        encoding="utf-8"
    )


def test_command_read_path_and_response_write_path_are_separated():
    text = source()

    # Command evidence remains read-only.
    assert "FileMode.Open" in text
    assert "FileAccess.Read" in text

    # Validation responses are create-once only.
    assert "FileMode.CreateNew" in text
    assert "FileAccess.Write" in text
    assert ".Flush(true)" in text

    # No destructive filesystem operations.
    forbidden = (
        "FileMode.Append",
        "FileMode.Truncate",
        "WriteAllText",
        "WriteAllBytes",
        "File.Delete(",
        "File.Move(",
        "File.Replace(",
    )

    for token in forbidden:
        assert token not in text


def test_native_skeleton_has_no_ack_file_surface():
    text = source()

    forbidden = (
        "AckDirectory",
        "acks",
        "write_ack",
        "WriteAck",
        "native_ack",
    )

    for token in forbidden:
        assert token not in text


def test_native_skeleton_has_no_order_objects():
    text = source()

    forbidden = (
        "OrderAction.",
        "OrderType.",
        "OrderState.",
        "TimeInForce.",
        "new Order",
        "Order order",
        "Execution execution",
    )

    for token in forbidden:
        assert token not in text


def test_native_skeleton_has_no_account_order_methods():
    text = source()

    forbidden = (
        ".CreateOrder",
        ".Submit",
        ".Cancel",
        ".Change",
        ".Flatten",
    )

    for token in forbidden:
        assert token not in text


def test_native_skeleton_only_accepts_simulator_provider():
    text = source()

    assert text.count(
        "Provider.Simulator"
    ) >= 2

    assert (
        "match.Provider != Provider.Simulator"
        in text
    )

    assert (
        "selectedAccount.Provider != Provider.Simulator"
        in text
    )


def test_native_skeleton_does_not_claim_execution():
    text = source()

    forbidden = (
        '"FILLED"',
        '"PARTIALLY_FILLED"',
        '"WORKING"',
        '"REJECTED"',
        '"ACKNOWLEDGED"',
        "accepted=true",
        "accepted = true",
    )

    for token in forbidden:
        assert token not in text

    assert "VALIDATED_NO_EXECUTION" in text


def test_native_skeleton_has_no_position_or_fill_projection():
    text = source()

    forbidden = (
        "Position.MarketPosition",
        "Account.Positions",
        ".Executions",
        "ExecutionUpdate",
        "OrderUpdate",
        '"fill_id"',
        '"filled_price"',
        '"position_id"',
    )

    for token in forbidden:
        assert token not in text


def test_command_scan_is_top_directory_only():
    text = source()

    assert (
        "SearchOption.TopDirectoryOnly"
        in text
    )

    assert (
        'Directory.GetFiles('
        in text
    )


def test_command_file_is_size_bounded():
    text = source()

    assert (
        "info.Length <= 0"
        in text
    )

    assert (
        "info.Length > 1024 * 1024"
        in text
    )


def test_runtime_does_not_auto_rebind_selected_account():
    text = source()

    # Account is resolved once during DataLoaded.
    assert (
        "selectedAccount = ResolveSelectedAccount();"
        in text
    )

    # OnBarUpdate only revalidates the pinned account.
    assert (
        "ValidateSelectedAccount();"
        in text
    )

    assert text.count(
        "ResolveSelectedAccount()"
    ) == 2
