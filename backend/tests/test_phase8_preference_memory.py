"""R109A explicit personal preferences remain session-only and nonexecuting."""

from dataclasses import replace

import pytest

from backend.medar.durable_memory_record import DurableMemoryDomain
from backend.medar.memory_candidates import CandidateSource, CandidateSourceType, MemoryCandidateExtractor
from backend.medar.preference_memory import PreferenceCategory, propose_explicit_preference


def _candidate(text):
    result = MemoryCandidateExtractor().extract(CandidateSource(
        "tenant-a", "owner-a", "conversation-1/turn-3",
        CandidateSourceType.USER_STATEMENT, DurableMemoryDomain.PREFERENCES, text,
    ))
    assert len(result.candidates) == 1
    return result.candidates[0]


@pytest.mark.parametrize("label, category", [
    ("language", PreferenceCategory.LANGUAGE), ("style", PreferenceCategory.STYLE),
    ("workflow", PreferenceCategory.WORKFLOW), ("tools", PreferenceCategory.TOOLS),
    ("notifications", PreferenceCategory.NOTIFICATIONS), ("risk", PreferenceCategory.RISK),
])
def test_explicit_preference_categories_are_proposal_only(label, category):
    candidate = _candidate(f"I prefer {label}: synthetic choice")
    proposal = propose_explicit_preference(candidate)
    assert proposal.category is category
    assert proposal.value == "synthetic choice"
    assert proposal.source_reference == "conversation-1/turn-3"
    assert proposal.value not in repr(proposal)
    assert proposal.session_only and not proposal.persistence_authorized
    assert not proposal.trading_authority


def test_unlabeled_or_inferred_personal_traits_are_not_promoted():
    with pytest.raises(ValueError, match="explicitly labeled"):
        propose_explicit_preference(_candidate("I prefer concise replies"))
    with pytest.raises(ValueError):
        propose_explicit_preference(replace(
            _candidate("I prefer risk: synthetic setting"), domain=DurableMemoryDomain.TECHNICAL,
        ))
