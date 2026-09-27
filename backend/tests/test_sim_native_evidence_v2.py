from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest

from backend.market_data.sim_native_evidence_v2 import (
    SimNativeEvidenceReaderV2,
)


NOW = datetime(2026, 9, 26, tzinfo=timezone.utc)

REF_A = "a" * 64
REF_B = "b" * 64
REF_C = "c" * 64
REF_D = "d" * 64


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


def frame(
    *,
    session,
    sequence=0,
    observed_at=None,
    provider="Simulator",
    connection_mode="Live",
    account_count=1,
    connected=True,
    revoked=False,
    installation_ref=REF_A,
    account_ref=REF_B,
    connection_ref=REF_C,
    label_ref=REF_D,
    runtime_ref="runtime-A",
    connection_epoch="epoch-A",
):
    return {
        "schema": "arms.nt.sim-operator-evidence.v2",
        "session": session,
        "sequence": sequence,
        "observed_at": (
            observed_at or NOW
        ).isoformat(),
        "payload": {
            "installation_ref": installation_ref,
            "account_ref": account_ref,
            "connection_ref": connection_ref,
            "label_ref": label_ref,
            "provider": provider,
            "connection_mode": connection_mode,
            "account_count": account_count,
            "connected": connected,
            "revoked": revoked,
            "runtime_ref": runtime_ref,
            "connection_epoch": connection_epoch,
        },
    }


def write_rows(path, rows):
    with Path(path).open("wb") as stream:
        for row in rows:
            stream.write(
                json.dumps(
                    row,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )


def test_reads_one_valid_native_scalar_snapshot(tmp_path):
    session = str(uuid4())
    path = tmp_path / f"{session}.sim-operator.jsonl"

    write_rows(
        path,
        [
            frame(
                session=session,
            )
        ],
    )

    reader = SimNativeEvidenceReaderV2(
        path=path.resolve(),
        clock=Clock(),
        maximum_age_seconds=15,
    )

    result = reader.poll()

    assert result == {
        "installation_ref": REF_A,
        "account_ref": REF_B,
        "connection_ref": REF_C,
        "label_ref": REF_D,
        "provider": "Simulator",
        "connection_mode": "Live",
        "account_count": 1,
        "connected": True,
        "revoked": False,
        "runtime_ref": "runtime-A",
        "connection_epoch": "epoch-A",
        "observed_at": NOW.isoformat(),
        "discovery_sequence": 0,
    }

    assert reader.session == session
    assert reader.sequence == 0


def test_sequence_is_strictly_contiguous(tmp_path):
    session = str(uuid4())
    path = tmp_path / f"{session}.sim-operator.jsonl"

    write_rows(
        path,
        [
            frame(
                session=session,
                sequence=1,
            )
        ],
    )

    reader = SimNativeEvidenceReaderV2(
        path=path.resolve(),
        clock=Clock(),
    )

    with pytest.raises(
        ValueError,
        match="SIM_NATIVE_EVIDENCE_RECOVERY_REQUIRED",
    ):
        reader.poll()


@pytest.mark.parametrize(
    "mutation",
    [
        {"provider": "Provider31"},
        {"connection_mode": "UNKNOWN"},
        {"account_count": 2},
        {"connected": False},
        {"installation_ref": "not-a-ref"},
        {"account_ref": "not-a-ref"},
        {"connection_ref": "not-a-ref"},
        {"label_ref": "not-a-ref"},
        {"runtime_ref": ""},
        {"connection_epoch": ""},
    ],
)
def test_invalid_sim_identity_payload_fails_closed(
    tmp_path,
    mutation,
):
    session = str(uuid4())
    path = tmp_path / f"{session}.sim-operator.jsonl"

    kwargs = {
        "session": session,
        **mutation,
    }

    write_rows(
        path,
        [frame(**kwargs)],
    )

    reader = SimNativeEvidenceReaderV2(
        path=path.resolve(),
        clock=Clock(),
    )

    with pytest.raises(
        ValueError,
        match="SIM_NATIVE_EVIDENCE_RECOVERY_REQUIRED",
    ):
        reader.poll()


def test_stale_or_future_event_fails_closed(tmp_path):
    for index, observed in enumerate(
        (
            NOW - timedelta(seconds=16),
            NOW + timedelta(seconds=1),
        )
    ):
        session = str(uuid4())
        path = tmp_path / (
            f"{index}-{session}.sim-operator.jsonl"
        )

        write_rows(
            path,
            [
                frame(
                    session=session,
                    observed_at=observed,
                )
            ],
        )

        reader = SimNativeEvidenceReaderV2(
            path=path.resolve(),
            clock=Clock(),
            maximum_age_seconds=15,
        )

        with pytest.raises(
            ValueError,
            match="SIM_NATIVE_EVIDENCE_RECOVERY_REQUIRED",
        ):
            reader.poll()


def test_duplicate_json_key_fails_closed(tmp_path):
    session = str(uuid4())
    path = tmp_path / f"{session}.sim-operator.jsonl"

    raw = (
        '{"schema":"arms.nt.sim-operator-evidence.v2",'
        f'"session":"{session}",'
        '"sequence":0,'
        '"sequence":0,'
        f'"observed_at":"{NOW.isoformat()}",'
        '"payload":{}}'
        "\n"
    )

    path.write_text(
        raw,
        encoding="utf-8",
    )

    reader = SimNativeEvidenceReaderV2(
        path=path.resolve(),
        clock=Clock(),
    )

    with pytest.raises(
        ValueError,
        match="SIM_NATIVE_EVIDENCE_RECOVERY_REQUIRED",
    ):
        reader.poll()


def test_extra_top_level_or_payload_field_fails_closed(tmp_path):
    for index, where in enumerate(
        ("top", "payload")
    ):
        session = str(uuid4())
        path = tmp_path / (
            f"{index}-{session}.sim-operator.jsonl"
        )

        value = frame(
            session=session,
        )

        if where == "top":
            value["extra"] = "forbidden"
        else:
            value["payload"]["extra"] = "forbidden"

        write_rows(
            path,
            [value],
        )

        reader = SimNativeEvidenceReaderV2(
            path=path.resolve(),
            clock=Clock(),
        )

        with pytest.raises(
            ValueError,
            match="SIM_NATIVE_EVIDENCE_RECOVERY_REQUIRED",
        ):
            reader.poll()


def test_reader_output_never_contains_raw_account_identifiers(
    tmp_path,
):
    session = str(uuid4())
    path = tmp_path / f"{session}.sim-operator.jsonl"

    write_rows(
        path,
        [
            frame(
                session=session,
            )
        ],
    )

    reader = SimNativeEvidenceReaderV2(
        path=path.resolve(),
        clock=Clock(),
    )

    result = reader.poll()

    forbidden = {
        "account_id",
        "account_name",
        "display_name",
        "balance",
        "orders",
        "positions",
        "executions",
    }

    assert not forbidden & set(result)


def test_reader_has_no_order_or_execution_authority_surface():
    import ast

    path = Path(
        "backend/market_data/sim_native_evidence_v2.py"
    )

    tree = ast.parse(
        path.read_text(encoding="utf-8")
    )

    forbidden = {
        "Submit",
        "submit_order",
        "CreateOrder",
        "Cancel",
        "Flatten",
        "ResetSimulationAccount",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
            else:
                name = getattr(
                    node.func,
                    "attr",
                    None,
                )

            assert name not in forbidden
