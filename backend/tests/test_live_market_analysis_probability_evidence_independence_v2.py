from backend.intelligence.confluence_engine_v2 import (
    ConfluenceEngineV2,
)
from backend.intelligence.probability_engine_v2 import (
    ProbabilityEngineV2,
)


def test_probability_v2_must_not_label_structure_as_independent_smart_money():
    """
    Canonical policy candidate:

    Probability V2 must not grant independent Smart Money
    authority to Confluence V2's structure_score.

    structure_score is already primary evidence inside
    Confluence V2, so treating it again as a separate 40%
    Smart Money component creates duplicate authority.
    """

    assert "structure" in ConfluenceEngineV2.WEIGHTS

    # Current runtime adapter maps:
    #
    # smart_money_score =
    #     confluence["structure_score"]
    #
    # Therefore a 40% Probability weight named smart_money
    # is not independent Smart Money evidence.
    assert (
        ProbabilityEngineV2.WEIGHTS.get(
            "smart_money",
            0.0,
        )
        == 0.0
    )


def test_probability_v2_should_not_directly_reweight_evidence_already_inside_confluence():
    """
    Canonical policy candidate:

    Once Probability V2 consumes canonical Confluence V2,
    trend, market regime and volume must not receive a second
    independent mathematical weight unless they represent
    genuinely independent evidence.

    Current runtime feeds the same canonical quality values
    both into Confluence V2 and directly into Probability V2.
    """

    duplicated_components = {
        "trend",
        "market_regime",
        "volume",
    }

    assert duplicated_components.issubset(
        ConfluenceEngineV2.WEIGHTS
    )

    for component in duplicated_components:
        assert (
            ProbabilityEngineV2.WEIGHTS.get(
                component,
                0.0,
            )
            == 0.0
        )


def test_probability_v2_should_preserve_full_probability_scale_after_deduplication():
    """
    Removing duplicate authority must not collapse the
    Probability V2 mathematical scale.

    The final canonical Probability weights must still total 1.
    """

    assert (
        sum(
            ProbabilityEngineV2.WEIGHTS.values()
        )
        == 1.0
    )


def test_canonical_architecture_removes_duplicate_structure_authority():
    """
    Canonical Gap #10 contract.

    Confluence V2 owns structure as primary evidence.
    Probability V2 must not assign a second independent
    mathematical weight to that same structure evidence.
    """

    assert (
        ConfluenceEngineV2.WEIGHTS[
            "structure"
        ]
        > 0.0
    )

    assert (
        ProbabilityEngineV2.WEIGHTS.get(
            "smart_money",
            0.0,
        )
        == 0.0
    )

    assert ProbabilityEngineV2.WEIGHTS == {
        "confluence": 1.0,
    }
