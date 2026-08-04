import pytest

from backend.backtesting.strategy_certification_engine_v2 import (
    StrategyCertificationEngineV2,
    StrategyCertificationResultV2,
)


def test_certifies_excellent_strategy():

    result = (
        StrategyCertificationEngineV2()
        .certify(
            validation_score=97.5,
            validation_grade="A+",
        )
    )

    assert isinstance(
        result,
        StrategyCertificationResultV2,
    )

    assert result.status == "CERTIFIED"

    assert result.reason == (
        "Strategy satisfies all certification requirements."
    )


def test_marks_strategy_as_provisional():

    result = (
        StrategyCertificationEngineV2()
        .certify(
            validation_score=84.0,
            validation_grade="B",
        )
    )

    assert result.status == "PROVISIONAL"

    assert result.reason == (
        "Strategy requires additional validation."
    )


def test_rejects_poor_strategy():

    result = (
        StrategyCertificationEngineV2()
        .certify(
            validation_score=58.0,
            validation_grade="F",
        )
    )

    assert result.status == "REJECTED"

    assert result.reason == (
        "Strategy does not satisfy minimum requirements."
    )


def test_to_dict_returns_safe_copy():

    result = (
        StrategyCertificationEngineV2()
        .certify(
            validation_score=95.0,
            validation_grade="A",
        )
    )

    payload = result.to_dict()

    payload["status"] = "INVALID"

    assert result.status == "CERTIFIED"


@pytest.mark.parametrize(
    "score",
    [
        None,
        object(),
        "95",
        True,
    ],
)
def test_rejects_invalid_score(score):

    with pytest.raises(
        TypeError,
        match="validation_score",
    ):
        StrategyCertificationEngineV2().certify(
            validation_score=score,
            validation_grade="A",
        )


@pytest.mark.parametrize(
    "grade",
    [
        "",
        " ",
        None,
        123,
    ],
)
def test_rejects_invalid_grade(grade):

    with pytest.raises(
        (
            TypeError,
            ValueError,
        ),
    ):
        StrategyCertificationEngineV2().certify(
            validation_score=90.0,
            validation_grade=grade,
        )
