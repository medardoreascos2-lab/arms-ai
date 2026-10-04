"""R108B structured session summary tests."""

import pytest

from backend.medar.session_summarization import SessionSummary, summarize_session
from backend.medar.session_working_memory import SessionWorkingMemory, TemporarySessionItem


def test_explicit_session_labels_become_traceable_structured_points():
    working = SessionWorkingMemory("session-1", "tenant-a", "owner-a")
    for index, line in enumerate((
        "Goal: finish migration", "Decision: keep rollback ready",
        "Fact: schema checksum passed", "Open task: run recovery test",
        "Outcome: focused tests passed", "unlabeled chatter",
    )):
        working.add_temporary(TemporarySessionItem(line, f"turn-{index}"))
    summary = summarize_session(working.snapshot())
    assert [point.text for point in summary.goals] == ["finish migration"]
    assert [point.text for point in summary.decisions] == ["keep rollback ready"]
    assert [point.text for point in summary.facts] == ["schema checksum passed"]
    assert [point.text for point in summary.open_tasks] == ["run recovery test"]
    assert [point.text for point in summary.outcomes] == ["focused tests passed"]
    assert summary.goals[0].source_reference == "turn-0"
    assert summary.omitted_items == 1
    assert not summary.hidden_chain_of_thought_stored and not summary.persistence_performed


def test_summary_caps_count_and_length_without_truncating_unverified_text():
    working = SessionWorkingMemory("session-1", "tenant-a", "owner-a")
    working.add_temporary(TemporarySessionItem("Goal: first", "turn-1"))
    working.add_temporary(TemporarySessionItem("Goal: second", "turn-2"))
    working.add_temporary(TemporarySessionItem("Fact: very long content", "turn-3"))
    summary = summarize_session(working.snapshot(), max_points=1, max_point_chars=10)
    assert [point.text for point in summary.goals] == ["first"]
    assert summary.facts == ()
    assert summary.omitted_items == 2
    with pytest.raises(ValueError):
        summarize_session(working.snapshot(), max_points=0)


def test_summary_omits_hidden_reasoning_and_cannot_claim_it_is_stored():
    working = SessionWorkingMemory("session-1", "tenant-a", "owner-a")
    working.add_temporary(TemporarySessionItem("Fact: hidden chain-of-thought follows", "turn-1"))
    summary = summarize_session(working.snapshot())
    assert summary.facts == ()
    assert summary.omitted_items == 1
    with pytest.raises(ValueError):
        SessionSummary("session-1", "tenant-a", "owner-a", (), (), (), (), (), 0, hidden_chain_of_thought_stored=True)
