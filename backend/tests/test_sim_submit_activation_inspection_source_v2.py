import json
from pathlib import Path

import pytest


MODULE = (
    "backend.services."
    "sim_submit_activation_inspection_source_v2"
)


def load_source():
    module = __import__(
        MODULE,
        fromlist=[
            "SimSubmitActivationInspectionSourceV2"
        ],
    )

    return (
        module
        .SimSubmitActivationInspectionSourceV2
    )


def write_activation(
    directory: Path,
    *,
    command_id="cmd-entry-1",
    operation_id="op-entry-1",
    client_order_id="op-entry-1",
    permit="ONE_SHOT_SIM101_V2",
    account="Sim101",
):
    path = (
        directory
        / f"{command_id}.arm.json"
    )

    path.write_text(
        json.dumps(
            {
                "command_id": command_id,
                "operation_id": operation_id,
                "client_order_id": client_order_id,
                "permit": permit,
                "account": account,
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    return path


def build(tmp_path):
    Source = load_source()

    return Source(
        activation_directory=tmp_path,
    )


def test_valid_activation_is_reported_read_only(tmp_path):
    write_activation(tmp_path)

    source = build(tmp_path)

    result = source.inspect(
        command_id="cmd-entry-1",
    )

    assert result == {
        "valid": True,
        "consumed": False,
        "command_id": "cmd-entry-1",
        "operation_id": "op-entry-1",
        "client_order_id": "op-entry-1",
        "permit": "ONE_SHOT_SIM101_V2",
        "account": "Sim101",
    }


def test_consumed_marker_is_reported(tmp_path):
    path = write_activation(tmp_path)

    Path(
        str(path) + ".consumed"
    ).write_text(
        "consumed\n",
        encoding="utf-8",
    )

    source = build(tmp_path)

    result = source.inspect(
        command_id="cmd-entry-1",
    )

    assert result["valid"] is True
    assert result["consumed"] is True


def test_missing_activation_fails_closed(tmp_path):
    source = build(tmp_path)

    with pytest.raises(RuntimeError):
        source.inspect(
            command_id="cmd-entry-1",
        )


def test_invalid_command_id_fails_closed(tmp_path):
    source = build(tmp_path)

    for value in (
        "",
        "../escape",
        "cmd entry",
        None,
    ):
        with pytest.raises(
            (TypeError, ValueError),
        ):
            source.inspect(
                command_id=value,
            )


def test_identity_mismatch_fails_closed(tmp_path):
    write_activation(
        tmp_path,
        command_id="cmd-entry-1",
        operation_id="op-entry-1",
        client_order_id="op-other",
    )

    source = build(tmp_path)

    with pytest.raises(RuntimeError):
        source.inspect(
            command_id="cmd-entry-1",
        )


def test_command_id_inside_file_must_match_filename(tmp_path):
    path = write_activation(
        tmp_path,
        command_id="cmd-entry-1",
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    payload["command_id"] = "cmd-other"

    path.write_text(
        json.dumps(
            payload,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    source = build(tmp_path)

    with pytest.raises(RuntimeError):
        source.inspect(
            command_id="cmd-entry-1",
        )


def test_permit_must_be_exact(tmp_path):
    write_activation(
        tmp_path,
        permit="OTHER",
    )

    source = build(tmp_path)

    with pytest.raises(RuntimeError):
        source.inspect(
            command_id="cmd-entry-1",
        )


def test_account_must_be_sim101(tmp_path):
    write_activation(
        tmp_path,
        account="Sim102",
    )

    source = build(tmp_path)

    with pytest.raises(RuntimeError):
        source.inspect(
            command_id="cmd-entry-1",
        )


def test_duplicate_json_keys_fail_closed(tmp_path):
    path = (
        tmp_path
        / "cmd-entry-1.arm.json"
    )

    path.write_text(
        (
            '{"command_id":"cmd-entry-1",'
            '"command_id":"cmd-entry-1",'
            '"operation_id":"op-entry-1",'
            '"client_order_id":"op-entry-1",'
            '"permit":"ONE_SHOT_SIM101_V2",'
            '"account":"Sim101"}'
        ),
        encoding="utf-8",
    )

    source = build(tmp_path)

    with pytest.raises(RuntimeError):
        source.inspect(
            command_id="cmd-entry-1",
        )


def test_extra_fields_fail_closed(tmp_path):
    path = write_activation(tmp_path)

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    payload["extra"] = True

    path.write_text(
        json.dumps(
            payload,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    source = build(tmp_path)

    with pytest.raises(RuntimeError):
        source.inspect(
            command_id="cmd-entry-1",
        )


def test_source_does_not_create_consumed_marker(tmp_path):
    path = write_activation(tmp_path)

    source = build(tmp_path)

    source.inspect(
        command_id="cmd-entry-1",
    )

    assert not Path(
        str(path) + ".consumed"
    ).exists()


def test_source_has_no_execution_surface(tmp_path):
    source = build(tmp_path)

    for forbidden in (
        "submit_order",
        "cancel_order",
        "modify_order",
        "close_position",
        "close_partial",
        "flatten",
        "execute",
        "consume",
        "arm",
    ):
        assert not hasattr(
            source,
            forbidden,
        )
