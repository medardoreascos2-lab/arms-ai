"""R85D MEDAR agent conflict handling tests."""

from backend.medar.agent_conflicts import ConflictStatus, assess_agent_conflict
from backend.medar.agent_contract import AgentOutput


def _output(agent_id, summary, evidence):
    return AgentOutput(agent_id, "task-1", summary, evidence, (), 0.7)


def test_disagreement_preserves_both_outputs_and_reports_uncertainty():
    first = _output("agent-a", "Option A is stronger", ("source-1", "source-a"))
    second = _output("agent-b", "Option B is stronger", ("source-1", "source-b"))

    assessment = assess_agent_conflict((first, second))

    assert assessment.status is ConflictStatus.DISAGREEMENT
    assert assessment.outputs == (first, second)
    assert assessment.shared_evidence == ("source-1",)
    assert assessment.differing_summaries == (first.summary, second.summary)
    assert assessment.uncertainty_reported is True
    assert assessment.selected_output is None


def test_consensus_may_select_first_output_without_discarding_others():
    first = _output("agent-a", "Same conclusion", ("source-1",))
    second = _output("agent-b", "Same conclusion", ("source-1", "source-2"))

    assessment = assess_agent_conflict((first, second))

    assert assessment.status is ConflictStatus.CONSENSUS
    assert assessment.selected_output is first
    assert assessment.outputs == (first, second)
    assert assessment.uncertainty_reported is False
