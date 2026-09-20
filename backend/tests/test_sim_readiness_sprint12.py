"""Future contracts only: no native account enumeration or order adapter."""
from dataclasses import fields, replace
from datetime import datetime, timezone

import pytest

from backend.market_data.sim_readiness_v1 import FutureSimGatesV1, OfflineOrderJournalV1, account_eligibility, decision_identity


def passing():
    return FutureSimGatesV1("PAPER_RESEARCH", "SIMULATION", True, True, "OPEN", "CONNECTED", *([True]*7))


@pytest.mark.parametrize("name", [f.name for f in fields(FutureSimGatesV1)])
@pytest.mark.parametrize("bad", [False, None, "true", 1])
def test_each_gate_veto_is_zero_external_authority(name,bad):
    result = replace(passing(), **{name:bad}).evaluate()
    assert not result["contract_satisfied"] and name.upper() in result["failed_gates"]
    assert result["external_order_authority"] is False


def test_even_all_passing_does_not_enable_orders():
    assert passing().evaluate() == dict(contract_satisfied=True,failed_gates=[],external_order_authority=False,sim_execution_authority="DISABLED")


@pytest.mark.parametrize("cls", ["SIMULATION", "REAL", "FUNDED", "EXTERNAL", "UNKNOWN", "Sim101", None])
def test_authoritative_metadata_required(cls):
    assert account_eligibility(cls) == "UNKNOWN_ACCOUNT_INELIGIBLE"
    expected = "SIM_ACCOUNT_ELIGIBLE" if cls == "SIMULATION" else "REAL_ACCOUNT_INELIGIBLE" if cls in {"REAL","FUNDED","EXTERNAL"} else "UNKNOWN_ACCOUNT_INELIGIBLE"
    assert account_eligibility(cls,authoritative=True) == expected


def identity():
    return decision_identity(namespace="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",contract="NQ TEST FIXTURE",
        decision_time=datetime(2026,9,14,14,tzinfo=timezone.utc),decision_id="fixture-decision")


@pytest.mark.parametrize("terminal", ["FILL", "CANCEL"])
def test_durable_duplicate_events_and_no_repeat_submission(tmp_path,terminal):
    path = tmp_path/"offline.sqlite"
    j = OfflineOrderJournalV1(path)
    key = identity()
    assert key == identity()
    for i, kind in enumerate(("DECISION","SUBMISSION","ACK",terminal)):
        assert j.record(key,str(i),kind)
        assert j.record(key,str(i),kind) is False
    assert j.record(key,"repeat-decision","DECISION") is False
    assert j.record(key,"repeat-submission","SUBMISSION") is False
    assert j.db.execute("SELECT count(*) FROM events").fetchone()[0] == 4
    j.close()
    j = OfflineOrderJournalV1(path)
    assert not j.recovery_required
    assert j.record(key,"3",terminal) is False
    assert j.record(key,"repeat-submission","SUBMISSION") is False
    j.close()


@pytest.mark.parametrize("case", ["restart_pending","reconnect","conflicting_ack","fill_without_decision","late_fill_after_cancel"])
def test_ambiguous_state_never_guesses_resubmission(tmp_path,case):
    path=tmp_path/"offline.sqlite"
    j=OfflineOrderJournalV1(path)
    key=identity()
    if case != "fill_without_decision":
        j.record(key,"d","DECISION")
        j.record(key,"s","SUBMISSION")
    if case == "restart_pending":
        j.close()
        j=OfflineOrderJournalV1(path)
    elif case == "reconnect": j.ambiguous_reconnect()
    else:
        if case == "late_fill_after_cancel": j.record(key,"c","CANCEL")
        with pytest.raises(RuntimeError,match="RECOVERY_REQUIRED"):
            j.record(key,"s" if case == "conflicting_ack" else "f", "ACK" if case == "conflicting_ack" else "FILL")
    assert j.recovery_required
    with pytest.raises(RuntimeError): j.record(key,"new","SUBMISSION")
    j.close()
    j=OfflineOrderJournalV1(path)
    assert j.recovery_required
    j.close()
