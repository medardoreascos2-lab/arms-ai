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
        assert "if (!String.IsNullOrWhiteSpace(OneClickBindingFile)) StartBindingWatcher();" in source
        assert "new System.Threading.Timer(_ => QueueBindingPoll(), null, 0, 500)" in source
        assert "TriggerCustomEvent(_ => PollBinding(), null)" in source
        assert "ResolveOneClickBinding(text);" in source
        assert '"arms.one-click-native-binding-control.v1"' in source
        assert '"ACTIVE"' in source
        assert '"arms.one-click-native-binding-claim.v1"' in source
        assert '"apply_limit"' in source


def test_passive_watchers_are_bounded_retry_safe_and_replay_protected():
    for source in (READ_ONLY, CATCHUP):
        assert "input.Length > 65536" in source
        assert "new UTF8Encoding(false, true)" in source
        assert "catch (IOException) { }" in source
        assert "catch (UnauthorizedAccessException) { }" in source
        assert "bindingGeneration <" in source or "bindingGeneration >=" in source
        assert "lastAcceptedBindingNonce" in source
        assert "lastAcceptedBindingClaimSha256" in source
        assert "lastAcceptedBindingRuntimeId" in source
        assert "lastAcceptedBindingRunId" in source
        assert 'state == "REVOKED"' in source
        assert "bindingGeneration == lastAcceptedBindingGeneration" in source


def test_passive_binding_validation_remains_fail_closed_and_observation_only():
    for source in (READ_ONLY, CATCHUP):
        assert "claim.Count == 32" in source or "claim.Count != 32" in source
        assert "TimeSpan.FromSeconds(900)" in source
        assert 'Text(claim, "expected_provider") != "Provider31"' in source or 'BindingText(claim, "expected_provider") == "Provider31"' in source
        assert '"NQ DEC26"' in source
        assert "FileAttributes.ReparsePoint" in source
        assert "bindingSessionActive = true" in source
        assert "revokedAuthorities.Any" in source


def test_read_only_passive_startup_requires_two_bounded_stable_snapshots():
    assert "ObserveStartupAlignmentSnapshot();" in READ_ONLY
    assert 'kind = "STARTUP_ALIGNMENT_SNAPSHOT"' in READ_ONLY
    assert 'ExpectedProvider == "Provider31"' in READ_ONLY
    assert "Object.ReferenceEquals(startupAlignmentSource, selected)" in READ_ONLY
    assert "if (separation < 250)" in READ_ONLY
    assert "if (separation > 1000)" in READ_ONLY
    assert 'AlignmentProvenance = "STARTUP_ALIGNMENT_STABLE_SNAPSHOT"' in READ_ONLY
    assert 'AlignmentProvenance = "STARTUP_ALIGNMENT_CALLBACK"' in READ_ONLY


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
