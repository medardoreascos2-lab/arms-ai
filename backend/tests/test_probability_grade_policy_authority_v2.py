from __future__ import annotations

import ast
import math
import os
from pathlib import Path

import pytest

from backend.config.api_settings import APISettings


VERY_HIGH_FIELD = "probability_very_high_threshold"
HIGH_FIELD = "probability_high_threshold"
MEDIUM_FIELD = "probability_medium_threshold"

VERY_HIGH_ENV = "ARMS_PROBABILITY_VERY_HIGH_THRESHOLD"
HIGH_ENV = "ARMS_PROBABILITY_HIGH_THRESHOLD"
MEDIUM_ENV = "ARMS_PROBABILITY_MEDIUM_THRESHOLD"

TARGET_ENVS = (
    VERY_HIGH_ENV,
    HIGH_ENV,
    MEDIUM_ENV,
)

UNRELATED_REQUIRED_ENV = {
    "ARMS_MAXIMUM_OPEN_POSITIONS": "4",
    "ARMS_MAXIMUM_QUOTE_AGE_SECONDS": "30",
    "ARMS_MAXIMUM_SIGNAL_AGE_SECONDS": "300",
    "ARMS_MAXIMUM_SPREAD_POINTS": "10",
    "ARMS_MAXIMUM_STOP_POINTS": "200",
    "ARMS_MINIMUM_ATR_POINTS": "1",
    "ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE": "0.8",
    "ARMS_MINIMUM_A_PLUS_PROBABILITY": "0.8",
    "ARMS_MINIMUM_EXECUTION_CONFIDENCE": "0.7",
    "ARMS_MINIMUM_PROBABILITY_APPROVAL": "0.8",
    "ARMS_MINIMUM_REWARD_RISK_RATIO": "1.5",
    "ARMS_MINIMUM_STOP_POINTS": "1",
    "ARMS_PAPER_EXECUTION_SLIPPAGE_POINTS": "0.25",
    "ARMS_TRAILING_STOP_ACTIVATION_POINTS": "30",
    "ARMS_TRAILING_STOP_DISTANCE_POINTS": "10",
}


def _prepare_env(
    monkeypatch: pytest.MonkeyPatch,
    **target_values: str,
) -> None:
    for key in tuple(os.environ):
        if key.startswith("ARMS_"):
            monkeypatch.delenv(
                key,
                raising=False,
            )

    for key, value in UNRELATED_REQUIRED_ENV.items():
        monkeypatch.setenv(
            key,
            value,
        )

    for key in TARGET_ENVS:
        monkeypatch.delenv(
            key,
            raising=False,
        )

    for key, value in target_values.items():
        monkeypatch.setenv(
            key,
            value,
        )


def _settings(
    monkeypatch: pytest.MonkeyPatch,
    **target_values: str,
) -> APISettings:
    _prepare_env(
        monkeypatch,
        **target_values,
    )
    return APISettings()


def _probability_engine_call() -> ast.Call:
    path = Path("backend/api/app.py")
    source = path.read_text(
        encoding="utf-8",
        errors="strict",
    )
    tree = ast.parse(source)

    calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            continue

        if name == "ProbabilityEngineV2":
            calls.append(node)

    assert len(calls) == 1
    return calls[0]


def _keyword_map(
    call: ast.Call,
) -> dict[str, str]:
    return {
        keyword.arg: ast.unparse(keyword.value)
        for keyword in call.keywords
        if keyword.arg is not None
    }


@pytest.mark.parametrize(
    ("field_name", "expected"),
    (
        (VERY_HIGH_FIELD, 0.90),
        (HIGH_FIELD, 0.80),
        (MEDIUM_FIELD, 0.65),
    ),
)
def test_probability_grade_policy_defaults_are_canonical(
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    expected: float,
) -> None:
    settings = _settings(monkeypatch)

    assert hasattr(
        settings,
        field_name,
    )
    assert getattr(
        settings,
        field_name,
    ) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("environment_name", "field_name", "value"),
    (
        (
            VERY_HIGH_ENV,
            VERY_HIGH_FIELD,
            "0.94",
        ),
        (
            HIGH_ENV,
            HIGH_FIELD,
            "0.78",
        ),
        (
            MEDIUM_ENV,
            MEDIUM_FIELD,
            "0.70",
        ),
    ),
)
def test_probability_grade_policy_env_overrides_are_canonical(
    monkeypatch: pytest.MonkeyPatch,
    environment_name: str,
    field_name: str,
    value: str,
) -> None:
    settings = _settings(
        monkeypatch,
        **{
            environment_name: value,
        },
    )

    assert getattr(
        settings,
        field_name,
    ) == pytest.approx(float(value))


@pytest.mark.parametrize(
    ("environment_name", "invalid_value"),
    tuple(
        (
            environment_name,
            invalid_value,
        )
        for environment_name in TARGET_ENVS
        for invalid_value in (
            "-0.01",
            "1.01",
            "nan",
            "inf",
            "-inf",
            "",
            "   ",
            "not-a-number",
        )
    ),
)
def test_probability_grade_policy_rejects_invalid_unit_interval_values(
    monkeypatch: pytest.MonkeyPatch,
    environment_name: str,
    invalid_value: str,
) -> None:
    _prepare_env(
        monkeypatch,
        **{
            environment_name: invalid_value,
        },
    )

    with pytest.raises(ValueError):
        APISettings()


@pytest.mark.parametrize(
    (
        "medium",
        "high",
        "approval",
        "very_high",
    ),
    (
        (
            "0.81",
            "0.80",
            "0.80",
            "0.90",
        ),
        (
            "0.65",
            "0.81",
            "0.80",
            "0.90",
        ),
        (
            "0.65",
            "0.80",
            "0.91",
            "0.90",
        ),
    ),
)
def test_probability_grade_policy_rejects_invalid_relations(
    monkeypatch: pytest.MonkeyPatch,
    medium: str,
    high: str,
    approval: str,
    very_high: str,
) -> None:
    _prepare_env(
        monkeypatch,
        **{
            MEDIUM_ENV: medium,
            HIGH_ENV: high,
            VERY_HIGH_ENV: very_high,
        },
    )

    monkeypatch.setenv(
        "ARMS_MINIMUM_PROBABILITY_APPROVAL",
        approval,
    )

    with pytest.raises(ValueError):
        APISettings()


def test_probability_grade_policy_accepts_boundary_equality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        **{
            MEDIUM_ENV: "0.80",
            HIGH_ENV: "0.80",
            VERY_HIGH_ENV: "0.80",
        },
    )

    assert settings.minimum_probability_approval == pytest.approx(
        0.80
    )
    assert getattr(
        settings,
        MEDIUM_FIELD,
    ) == pytest.approx(0.80)
    assert getattr(
        settings,
        HIGH_FIELD,
    ) == pytest.approx(0.80)
    assert getattr(
        settings,
        VERY_HIGH_FIELD,
    ) == pytest.approx(0.80)


@pytest.mark.parametrize(
    ("keyword_name", "settings_expression"),
    (
        (
            "very_high_threshold",
            "settings.probability_very_high_threshold",
        ),
        (
            "high_threshold",
            "settings.probability_high_threshold",
        ),
        (
            "medium_threshold",
            "settings.probability_medium_threshold",
        ),
    ),
)
def test_probability_engine_app_wiring_uses_canonical_settings(
    keyword_name: str,
    settings_expression: str,
) -> None:
    values = _keyword_map(
        _probability_engine_call()
    )

    assert values[keyword_name] == settings_expression


def test_probability_engine_app_preserves_existing_approval_authority(
) -> None:
    values = _keyword_map(
        _probability_engine_call()
    )

    assert (
        values["minimum_approval_probability"]
        == "settings.minimum_probability_approval"
    )


def test_probability_grade_policy_fields_are_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        **{
            VERY_HIGH_ENV: "0.95",
            HIGH_ENV: "0.79",
            MEDIUM_ENV: "0.70",
        },
    )

    assert getattr(
        settings,
        VERY_HIGH_FIELD,
    ) == pytest.approx(0.95)
    assert getattr(
        settings,
        HIGH_FIELD,
    ) == pytest.approx(0.79)
    assert getattr(
        settings,
        MEDIUM_FIELD,
    ) == pytest.approx(0.70)

    assert settings.minimum_probability_approval == pytest.approx(
        0.80
    )


def test_probability_grade_policy_values_are_finite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)

    values = (
        getattr(
            settings,
            VERY_HIGH_FIELD,
        ),
        getattr(
            settings,
            HIGH_FIELD,
        ),
        getattr(
            settings,
            MEDIUM_FIELD,
        ),
    )

    assert all(
        math.isfinite(float(value))
        for value in values
    )
