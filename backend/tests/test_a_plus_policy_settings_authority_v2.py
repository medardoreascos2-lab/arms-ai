from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from backend.api.app import create_app
from backend.config.api_settings import APISettings


PROBABILITY_ENV = "ARMS_MINIMUM_A_PLUS_PROBABILITY"
CONFLUENCE_ENV = "ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE"


def _configure_required_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    probability: str = "0.85",
    confluence: str = "0.86",
) -> None:
    monkeypatch.setenv(
        "ARMS_MAXIMUM_QUOTE_AGE_SECONDS",
        "5.0",
    )
    monkeypatch.setenv(
        "ARMS_MINIMUM_REWARD_RISK_RATIO",
        "2.0",
    )
    monkeypatch.setenv(
        "ARMS_MINIMUM_STOP_POINTS",
        "2.0",
    )
    monkeypatch.setenv(
        "ARMS_MAXIMUM_STOP_POINTS",
        "50.0",
    )
    monkeypatch.setenv(
        "ARMS_MAXIMUM_SPREAD_POINTS",
        "1.0",
    )
    monkeypatch.setenv(
        "ARMS_MINIMUM_ATR_POINTS",
        "3.0",
    )
    monkeypatch.setenv(
        "ARMS_MAXIMUM_SIGNAL_AGE_SECONDS",
        "30",
    )
    monkeypatch.setenv(
        PROBABILITY_ENV,
        probability,
    )
    monkeypatch.setenv(
        CONFLUENCE_ENV,
        confluence,
    )


def _production_gate_calls() -> dict[str, ast.Call]:
    path = Path("backend/api/app.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    targets = {
        "SignalGeneratorV2",
        "ExecutionDecisionEngineV2",
    }
    calls: dict[str, list[ast.Call]] = {
        name: []
        for name in targets
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        try:
            name = ast.unparse(node.func).split(".")[-1]
        except Exception:
            continue

        if name in calls:
            calls[name].append(node)

    assert all(
        len(found) == 1
        for found in calls.values()
    )

    return {
        name: found[0]
        for name, found in calls.items()
    }


def _keyword_authorities(
    call: ast.Call,
) -> dict[str, str]:
    return {
        keyword.arg: ast.unparse(keyword.value)
        for keyword in call.keywords
        if keyword.arg is not None
    }


def test_a_plus_policy_settings_read_explicit_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_required_environment(
        monkeypatch,
        probability="0.85",
        confluence="0.86",
    )

    settings = APISettings()

    assert (
        settings.minimum_a_plus_probability
        == pytest.approx(0.85)
    )
    assert (
        settings.minimum_a_plus_confluence_score
        == pytest.approx(0.86)
    )
    assert math.isfinite(
        settings.minimum_a_plus_probability
    )
    assert math.isfinite(
        settings.minimum_a_plus_confluence_score
    )


@pytest.mark.parametrize(
    ("env_name", "raw_value"),
    [
        (PROBABILITY_ENV, ""),
        (PROBABILITY_ENV, "abc"),
        (PROBABILITY_ENV, "nan"),
        (PROBABILITY_ENV, "inf"),
        (PROBABILITY_ENV, "-0.01"),
        (PROBABILITY_ENV, "1.01"),
        (CONFLUENCE_ENV, ""),
        (CONFLUENCE_ENV, "abc"),
        (CONFLUENCE_ENV, "nan"),
        (CONFLUENCE_ENV, "inf"),
        (CONFLUENCE_ENV, "-0.01"),
        (CONFLUENCE_ENV, "1.01"),
    ],
)
def test_a_plus_policy_settings_reject_invalid_environment(
    monkeypatch: pytest.MonkeyPatch,
    env_name: str,
    raw_value: str,
) -> None:
    _configure_required_environment(
        monkeypatch
    )
    monkeypatch.setenv(
        env_name,
        raw_value,
    )

    with pytest.raises(
        (TypeError, ValueError),
        match=env_name,
    ):
        APISettings()


def test_production_gates_use_single_settings_authority() -> None:
    calls = _production_gate_calls()

    expected = {
        "minimum_probability":
            "settings.minimum_a_plus_probability",
        "minimum_confluence_score":
            "settings.minimum_a_plus_confluence_score",
    }

    for name in (
        "SignalGeneratorV2",
        "ExecutionDecisionEngineV2",
    ):
        actual = _keyword_authorities(
            calls[name]
        )

        assert {
            key: actual.get(key)
            for key in expected
        } == expected


def test_production_gates_have_no_a_plus_policy_literals() -> None:
    calls = _production_gate_calls()

    for name, call in calls.items():
        matching = [
            keyword
            for keyword in call.keywords
            if keyword.arg in {
                "minimum_probability",
                "minimum_confluence_score",
            }
        ]

        assert len(matching) == 2

        for keyword in matching:
            assert not isinstance(
                keyword.value,
                ast.Constant,
            ), (
                f"{name}.{keyword.arg} todavía "
                "usa un literal productivo."
            )


def test_runtime_gates_share_a_plus_policy_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_required_environment(
        monkeypatch,
        probability="0.85",
        confluence="0.86",
    )

    settings = APISettings()
    app = create_app(settings=settings)

    signal = app.state.signal_generator_v2
    execution = (
        app.state.execution_decision_engine_v2
    )

    assert (
        signal.minimum_probability
        == execution.minimum_probability
        == settings.minimum_a_plus_probability
        == pytest.approx(0.85)
    )

    assert (
        signal.minimum_confluence_score
        == execution.minimum_confluence_score
        == settings.minimum_a_plus_confluence_score
        == pytest.approx(0.86)
    )
