import pytest

from backend.backtesting.validation_grade_engine_v2 import (
    ValidationGradeEngineV2,
    ValidationGradeResultV2,
)


@pytest.mark.parametrize(
    ("score", "expected_grade"),
    [
        (100.0, "A+"),
        (98.0, "A+"),
        (95.0, "A"),
        (91.0, "A-"),
        (88.0, "B+"),
        (84.0, "B"),
        (81.0, "B-"),
        (77.0, "C+"),
        (72.0, "C"),
        (65.0, "D"),
        (40.0, "F"),
        (0.0, "F"),
    ],
)
def test_assigns_expected_grade(
    score,
    expected_grade,
):

    engine = ValidationGradeEngineV2()

    result = engine.calculate(
        validation_score=score,
    )

    assert isinstance(
        result,
        ValidationGradeResultV2,
    )

    assert result.grade == expected_grade


def test_recommendation_for_excellent_strategy():

    result = ValidationGradeEngineV2().calculate(
        validation_score=96.0,
    )

    assert (
        result.recommendation
        == "READY FOR LIVE DEPLOYMENT"
    )


def test_recommendation_for_average_strategy():

    result = ValidationGradeEngineV2().calculate(
        validation_score=82.0,
    )

    assert (
        result.recommendation
        == "NEEDS IMPROVEMENT"
    )


def test_recommendation_for_poor_strategy():

    result = ValidationGradeEngineV2().calculate(
        validation_score=55.0,
    )

    assert (
        result.recommendation
        == "REJECT STRATEGY"
    )


def test_to_dict_returns_safe_copy():

    result = ValidationGradeEngineV2().calculate(
        validation_score=95.0,
    )

    payload = result.to_dict()

    payload["grade"] = "X"

    assert result.grade == "A"


@pytest.mark.parametrize(
    "score",
    [
        None,
        object(),
        "95",
        True,
    ],
)
def test_rejects_invalid_score(
    score,
):

    with pytest.raises(
        TypeError,
        match="validation_score",
    ):
        ValidationGradeEngineV2().calculate(
            validation_score=score,
        )


def test_clamps_scores():

    engine = ValidationGradeEngineV2()

    assert (
        engine.calculate(
            validation_score=150.0,
        ).grade
        == "A+"
    )

    assert (
        engine.calculate(
            validation_score=-20.0,
        ).grade
        == "F"
    )
