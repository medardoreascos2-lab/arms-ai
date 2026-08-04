import pytest

from backend.backtesting.validation_score_engine_v2 import (
    ValidationScoreEngineV2,
    ValidationScoreResultV2,
)


def test_calculates_weighted_validation_score():

    engine = ValidationScoreEngineV2(
        backtest_weight=0.40,
        walk_forward_weight=0.35,
        monte_carlo_weight=0.25,
    )

    result = engine.calculate(
        backtest_score=90.0,
        walk_forward_score=80.0,
        monte_carlo_score=70.0,
    )

    assert isinstance(
        result,
        ValidationScoreResultV2,
    )

    assert result.score == pytest.approx(
        81.5
    )

    assert result.components == {
        "backtest": pytest.approx(
            36.0
        ),
        "walk_forward": pytest.approx(
            28.0
        ),
        "monte_carlo": pytest.approx(
            17.5
        ),
    }


def test_default_weights_are_balanced():

    engine = ValidationScoreEngineV2()

    result = engine.calculate(
        backtest_score=90.0,
        walk_forward_score=80.0,
        monte_carlo_score=70.0,
    )

    assert result.score == pytest.approx(
        80.0
    )


def test_clamps_input_scores_to_valid_range():

    engine = ValidationScoreEngineV2()

    result = engine.calculate(
        backtest_score=120.0,
        walk_forward_score=-10.0,
        monte_carlo_score=50.0,
    )

    assert 0.0 <= result.score <= 100.0

    assert result.normalized_scores == {
        "backtest": 100.0,
        "walk_forward": 0.0,
        "monte_carlo": 50.0,
    }


def test_to_dict_returns_safe_copy():

    result = ValidationScoreEngineV2().calculate(
        backtest_score=90.0,
        walk_forward_score=80.0,
        monte_carlo_score=70.0,
    )

    payload = result.to_dict()

    payload["components"][
        "backtest"
    ] = 0.0

    assert (
        result.components["backtest"]
        != 0.0
    )


@pytest.mark.parametrize(
    (
        "backtest_weight",
        "walk_forward_weight",
        "monte_carlo_weight",
    ),
    [
        (-0.1, 0.6, 0.5),
        (0.4, -0.1, 0.7),
        (0.4, 0.7, -0.1),
    ],
)
def test_rejects_negative_weights(
    backtest_weight,
    walk_forward_weight,
    monte_carlo_weight,
):

    with pytest.raises(
        ValueError,
        match="weight",
    ):
        ValidationScoreEngineV2(
            backtest_weight=(
                backtest_weight
            ),
            walk_forward_weight=(
                walk_forward_weight
            ),
            monte_carlo_weight=(
                monte_carlo_weight
            ),
        )


def test_rejects_weights_not_summing_to_one():

    with pytest.raises(
        ValueError,
        match="sumar 1.0",
    ):
        ValidationScoreEngineV2(
            backtest_weight=0.50,
            walk_forward_weight=0.30,
            monte_carlo_weight=0.30,
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "90",
        object(),
        True,
    ],
)
def test_rejects_invalid_scores(
    value,
):

    engine = ValidationScoreEngineV2()

    with pytest.raises(
        TypeError,
        match="score",
    ):
        engine.calculate(
            backtest_score=value,
            walk_forward_score=80.0,
            monte_carlo_score=70.0,
        )


def test_rounds_score_to_two_decimals():

    engine = ValidationScoreEngineV2(
        backtest_weight=0.34,
        walk_forward_weight=0.33,
        monte_carlo_weight=0.33,
    )

    result = engine.calculate(
        backtest_score=87.123,
        walk_forward_score=81.456,
        monte_carlo_score=75.789,
    )

    assert result.score == round(
        result.score,
        2,
    )
