from dataclasses import dataclass

import pytest

from backend.backtesting.walk_forward_parameter_selector import (
    WalkForwardParameterSelector,
)


@dataclass(frozen=True)
class Candidate:
    name: str
    net_profit: float
    max_drawdown: float = 0.0


def test_selector_chooses_highest_net_profit():
    selector = WalkForwardParameterSelector(
        metric="net_profit",
    )

    selected = selector.select(
        candidates=[
            Candidate("A", 10.0),
            Candidate("B", 25.0),
            Candidate("C", -5.0),
        ]
    )

    assert selected.name == "B"


def test_selector_chooses_lowest_drawdown():
    selector = WalkForwardParameterSelector(
        metric="max_drawdown",
        maximize=False,
    )

    selected = selector.select(
        candidates=[
            Candidate("A", 10.0, 8.0),
            Candidate("B", 20.0, 3.0),
            Candidate("C", 15.0, 5.0),
        ]
    )

    assert selected.name == "B"


def test_selector_preserves_first_candidate_on_tie():
    selector = WalkForwardParameterSelector(
        metric="net_profit",
    )

    first = Candidate("A", 10.0)
    second = Candidate("B", 10.0)

    selected = selector.select(
        candidates=[
            first,
            second,
        ]
    )

    assert selected is first


def test_selector_rejects_empty_candidates():
    selector = WalkForwardParameterSelector(
        metric="net_profit",
    )

    with pytest.raises(
        ValueError,
        match="candidates",
    ):
        selector.select(candidates=[])


def test_selector_rejects_missing_metric():
    selector = WalkForwardParameterSelector(
        metric="profit_factor",
    )

    with pytest.raises(
        ValueError,
        match="profit_factor",
    ):
        selector.select(
            candidates=[
                Candidate("A", 10.0),
            ]
        )


def test_selector_requires_metric_name():
    with pytest.raises(
        ValueError,
        match="metric",
    ):
        WalkForwardParameterSelector(
            metric="",
        )
