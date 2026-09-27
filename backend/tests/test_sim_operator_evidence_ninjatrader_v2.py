from pathlib import Path
import re


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimOperatorEvidenceV2.cs"
)


def source():
    return SOURCE.read_text(encoding="utf-8")


def test_native_sim_operator_emitter_exists_and_is_read_only():
    text = source()

    assert "class ArmsSimOperatorEvidenceV2" in text
    assert "arms.nt.sim-operator-evidence.v2" in text

    forbidden = (
        ".Submit(",
        ".CreateOrder(",
        ".Change(",
        ".Cancel(",
        "CancelAllOrders",
        ".Flatten(",
        "FlattenEverything",
        "ResetSimulationAccount",
        "GetAccountItem",
        ".Orders",
        ".Positions",
        ".Executions",
    )

    for token in forbidden:
        assert token not in text


def test_operator_must_explicitly_select_exactly_one_account():
    text = source()

    assert "SelectedAccountName" in text
    assert "Account.All" in text

    assert re.search(
        r"Monitor\.TryEnter\s*\(\s*Account\.All\s*\)",
        text,
        re.S,
    )

    assert re.search(
        r"\.Where\s*\([^)]*SelectedAccountName",
        text,
        re.S,
    )

    assert (
        "candidates.Length == 1" in text
        or "candidates.Length != 1" in text
    )


def test_native_simulation_classification_uses_account_provider_and_observes_connection_mode():
    text = source()

    assert "Provider.Simulator" in text
    assert ".Provider" in text
    assert ".Options.Mode" in text
    assert "connection_mode" in text
    assert "ConnectionStatus.Connected" in text


def test_emitter_uses_hmac_sha256_not_plain_sha256_for_private_refs():
    text = source()

    assert "System.Security.Cryptography" in text
    assert "HMACSHA256" in text

    for domain in (
        "installation",
        "account",
        "connection",
        "label",
    ):
        assert f'"{domain}"' in text

    assert "installation_ref" in text
    assert "account_ref" in text
    assert "connection_ref" in text
    assert "label_ref" in text


def test_secret_is_loaded_from_explicit_private_file_and_never_serialized():
    text = source()

    assert "SecretPath" in text
    assert "File.ReadAllBytes" in text

    forbidden_serialized_names = (
        "secret =",
        "secret=",
        "secret_path =",
        "secret_path=",
        "SecretPath =",
    )

    serializer_regions = [
        line
        for line in text.splitlines()
        if "Serialize(" in line or "writer.WriteLine" in line
    ]

    joined = "\n".join(serializer_regions)

    for token in forbidden_serialized_names:
        assert token not in joined


def test_runtime_and_connection_epoch_are_fresh_and_never_rebound():
    text = source()

    assert "runtimeRef" in text
    assert "connectionEpoch" in text
    assert text.count("Guid.NewGuid()") >= 3

    assert re.search(
        r"Connection\.ConnectionStatusUpdate\s*\+=",
        text,
        re.S,
    )

    assert re.search(
        r"Connection\.ConnectionStatusUpdate\s*-=",
        text,
        re.S,
    )

    for status in (
        "ConnectionStatus.Disconnected",
        "ConnectionStatus.Disconnecting",
        "ConnectionStatus.ConnectionLost",
    ):
        assert status in text

    assert (
        "CONNECTION_EPOCH_REVOKED" in text
        or "CONNECTION_LOST" in text
    )


def test_jsonl_contract_contains_only_scalar_binding_evidence():
    text = source()

    required = (
        "schema",
        "session",
        "sequence",
        "observed_at",
        "installation_ref",
        "account_ref",
        "connection_ref",
        "label_ref",
        "provider",
        "connection_mode",
        "account_count",
        "connected",
        "revoked",
        "runtime_ref",
        "connection_epoch",
    )

    for name in required:
        assert name in text

    forbidden = (
        "balance",
        "equity",
        "realized_pnl",
        "unrealized_pnl",
        "order_id",
        "position_id",
        "execution_id",
    )

    # Ignore comments when checking forbidden serialized/data surfaces.
    executable = re.sub(
        r"//.*?$|/\*.*?\*/",
        "",
        text,
        flags=re.M | re.S,
    ).lower()

    for name in forbidden:
        assert name not in executable


def test_output_file_is_create_new_utf8_and_share_read_only():
    text = source()

    assert "FileMode.CreateNew" in text
    assert "FileAccess.Write" in text
    assert "FileShare.Read" in text
    assert "new UTF8Encoding(false)" in text
    assert "AutoFlush = true" in text


def test_emitter_never_claims_builtin_sim101_proof_or_execution_authority():
    text = source()

    assert "builtin_sim101_proof" not in text

    forbidden_claims = (
        'sim_execution_authority = "ENABLED"',
        "external_order_authority = true",
        "live_authority = true",
    )

    for claim in forbidden_claims:
        assert claim not in text
