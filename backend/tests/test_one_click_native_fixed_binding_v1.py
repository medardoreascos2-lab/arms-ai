"""Static safety contract for the optional native One Click binding mode."""

from pathlib import Path


READ_ONLY = Path(
    "integrations/ninjatrader/ArmsReadOnlyMarketV1.cs"
).read_text(encoding="utf-8")
CATCHUP = Path(
    "integrations/ninjatrader/ArmsChartCatchupBridgeV1.cs"
).read_text(encoding="utf-8")


def test_both_indicators_use_the_same_optional_active_binding_contract():
    for source in (READ_ONLY, CATCHUP):
        assert "public string OneClickBindingFile { get; set; }" in source
        assert 'OneClickBindingFile = "";' in source
        assert "if (!String.IsNullOrWhiteSpace(OneClickBindingFile)) ResolveOneClickBinding();" in source
        assert '"arms.one-click-native-binding-control.v1"' in source
        assert '"ACTIVE"' in source
        assert '"arms.one-click-native-binding-claim.v1"' in source
        assert '"apply_limit"' in source


def test_binding_paths_are_exact_uuid_children_and_reparse_points_are_blocked():
    for source in (READ_ONLY, CATCHUP):
        assert 'Path.Combine(runtime, "inbox")' in source
        assert 'Path.Combine(runtime, "chart-catchup")' in source
        assert "Guid.TryParseExact(runtimeId, \"D\"" in source
        assert "FileAttributes.ReparsePoint" in source
        assert "DriveType.Fixed" in source
        assert '"one-click-native-control"' in source


def test_read_only_receipt_binds_hello_lineage_without_changing_hello_payload():
    assert '"arms.nt.one-click-binding-receipt.v1"' in READ_ONLY
    assert 'session + ".one-click-binding.json"' in READ_ONLY
    assert "WriteBindingReceipt();" in READ_ONLY
    assert 'Emit("HELLO", new { provider = ExpectedProvider' in READ_ONLY
    assert '"arms.nt.one-click-binding-receipt.v1"' in CATCHUP
    assert "ValidateBindingReceipt(" in CATCHUP


def test_binding_mode_contains_no_execution_or_workspace_mutation_surface():
    forbidden = (
        "EnterLong", "EnterShort", "SubmitOrder", "Account.CreateOrder",
        "ChangeOrder", "CancelOrder", "Workspaces.xml", "workspace.xml",
    )
    for source in (READ_ONLY, CATCHUP):
        assert not any(token in source for token in forbidden)
        for authority in (
            "paper_execution_enabled", "live_execution_allowed",
            "external_order_authority", "broker_live_order_authority",
            "execution_authority", "order_authority",
            "strategy_enable_authority", "ninjatrader_control_authority",
        ):
            assert authority in source
