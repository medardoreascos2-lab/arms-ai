from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

from backend.market_data.sim_native_evidence_v2 import (
    SimNativeEvidenceReaderV2,
)
from backend.market_data.sim_operator_binding_v2 import (
    OperatorSimBindingV2,
    OperatorSimBindingLatchV2,
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


def row(session, sequence, observed_at, *, connection_ref=REF_C):
    return {
        "schema": "arms.nt.sim-operator-evidence.v2",
        "session": session,
        "sequence": sequence,
        "observed_at": observed_at.isoformat(),
        "payload": {
            "installation_ref": REF_A,
            "account_ref": REF_B,
            "connection_ref": connection_ref,
            "label_ref": REF_D,
            "provider": "Simulator",
            "connection_mode": "Live",
            "account_count": 1,
            "connected": True,
            "revoked": False,
            "runtime_ref": "runtime-A",
            "connection_epoch": "epoch-A",
        },
    }


def append(path, value):
    with Path(path).open("ab") as stream:
        stream.write(
            json.dumps(
                value,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )


def binding():
    return OperatorSimBindingV2(
        installation_ref=REF_A,
        account_ref=REF_B,
        connection_ref=REF_C,
        label_ref=REF_D,
        provider="Simulator",
        connection_mode="Live",
        enabled=True,
        operator_approved=True,
    )


def test_native_reader_to_binding_latch_pipeline(tmp_path):
    session = str(uuid4())
    path = tmp_path / f"{session}.sim-operator.jsonl"
    path.touch()

    clock = Clock()

    reader = SimNativeEvidenceReaderV2(
        path=path.resolve(),
        clock=clock,
    )

    latch = OperatorSimBindingLatchV2(
        binding(),
        runtime_ref="runtime-A",
        connection_epoch="epoch-A",
    )

    append(
        path,
        row(
            session,
            0,
            NOW,
        ),
    )

    snapshot = reader.poll()
    result = latch.observe(
        snapshot,
        NOW,
    )

    assert result["future_sim_eligible"] is True
    assert result["sim_classification_status"] == "PROVEN_SIMULATION"
    assert result["sim_binding_status"] == "BOUND"
    assert result["sim_runtime_revalidation"] == "PASS"

    assert result["sim_execution_authority"] == "DISABLED"
    assert result["external_order_authority"] is False

    clock.now = NOW + timedelta(seconds=1)

    append(
        path,
        row(
            session,
            1,
            clock.now,
        ),
    )

    snapshot = reader.poll()
    result = latch.observe(
        snapshot,
        clock.now,
    )

    assert result["future_sim_eligible"] is True
    assert result["sim_runtime_revalidation"] == "PASS"
    assert result["sim_execution_authority"] == "DISABLED"


def test_native_identity_drift_revokes_pipeline(tmp_path):
    session = str(uuid4())
    path = tmp_path / f"{session}.sim-operator.jsonl"
    path.touch()

    clock = Clock()

    reader = SimNativeEvidenceReaderV2(
        path=path.resolve(),
        clock=clock,
    )

    latch = OperatorSimBindingLatchV2(
        binding(),
        runtime_ref="runtime-A",
        connection_epoch="epoch-A",
    )

    append(
        path,
        row(
            session,
            0,
            NOW,
        ),
    )

    first = latch.observe(
        reader.poll(),
        NOW,
    )

    assert first["future_sim_eligible"] is True

    clock.now = NOW + timedelta(seconds=1)

    append(
        path,
        row(
            session,
            1,
            clock.now,
            connection_ref="e" * 64,
        ),
    )

    second = latch.observe(
        reader.poll(),
        clock.now,
    )

    assert second["future_sim_eligible"] is False
    assert second["sim_runtime_revalidation"] == "REVOKED"
    assert second["sim_execution_authority"] == "DISABLED"
    assert second["external_order_authority"] is False
