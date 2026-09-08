from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from backend.config.api_settings import APISettings


APP_PATH = Path("backend/api/app.py")
SETTINGS_PATH = Path("backend/config/api_settings.py")

ACTIVATION_ENV = "ARMS_TRAILING_STOP_ACTIVATION_POINTS"
DISTANCE_ENV = "ARMS_TRAILING_STOP_DISTANCE_POINTS"

REQUIRED_BASE_ENV = {
    "ARMS_MAXIMUM_OPEN_POSITIONS": "1",
    "ARMS_MAXIMUM_QUOTE_AGE_SECONDS": "5.0",
    "ARMS_MAXIMUM_SIGNAL_AGE_SECONDS": "60",
    "ARMS_MAXIMUM_SPREAD_POINTS": "5.0",
    "ARMS_MAXIMUM_STOP_POINTS": "500.0",
    "ARMS_MINIMUM_ATR_POINTS": "1.0",
    "ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE": "0.80",
    "ARMS_MINIMUM_A_PLUS_PROBABILITY": "0.80",
    "ARMS_MINIMUM_REWARD_RISK_RATIO": "2.0",
    "ARMS_MINIMUM_STOP_POINTS": "1.0",
}


def _configure_required_base_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in REQUIRED_BASE_ENV.items():
        monkeypatch.setenv(name, value)

    monkeypatch.delenv(
        "ARMS_MINIMUM_EXECUTION_CONFIDENCE",
        raising=False,
    )
    monkeypatch.delenv(
        "ARMS_MINIMUM_PROBABILITY_APPROVAL",
        raising=False,
    )


def _trailing_stop_call_keywords() -> dict[str, str]:
    source = APP_PATH.read_text(
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

        if name == "TrailingStopEngineV2":
            calls.append(node)

    assert len(calls) == 1

    return {
        keyword.arg: ast.unparse(keyword.value)
        for keyword in calls[0].keywords
        if keyword.arg is not None
    }


def test_api_settings_owns_independent_trailing_stop_policy() -> None:
    annotations = getattr(
        APISettings,
        "__annotations__",
        {},
    )

    assert "trailing_stop_activation_points" in annotations
    assert "trailing_stop_distance_points" in annotations


def test_trailing_stop_policy_environment_names_are_canonical() -> None:
    source = SETTINGS_PATH.read_text(
        encoding="utf-8",
        errors="strict",
    )

    assert ACTIVATION_ENV in source
    assert DISTANCE_ENV in source


def test_production_trailing_stop_consumes_settings_authority() -> None:
    keywords = _trailing_stop_call_keywords()

    assert keywords["activation_profit_points"] == (
        "settings.trailing_stop_activation_points"
    )
    assert keywords["trailing_distance_points"] == (
        "settings.trailing_stop_distance_points"
    )


def test_production_trailing_stop_literals_are_removed() -> None:
    keywords = _trailing_stop_call_keywords()

    assert keywords["activation_profit_points"] not in {
        "30",
        "30.0",
    }

    assert keywords["trailing_distance_points"] not in {
        "10",
        "10.0",
    }


def test_default_trailing_stop_policy_preserves_production_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_required_base_env(monkeypatch)

    monkeypatch.delenv(
        ACTIVATION_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        DISTANCE_ENV,
        raising=False,
    )

    settings = APISettings()

    assert settings.trailing_stop_activation_points == 30.0
    assert settings.trailing_stop_distance_points == 10.0


def test_custom_trailing_stop_policy_is_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_required_base_env(monkeypatch)

    monkeypatch.setenv(
        ACTIVATION_ENV,
        "45.0",
    )
    monkeypatch.setenv(
        DISTANCE_ENV,
        "15.0",
    )

    settings = APISettings()

    assert settings.trailing_stop_activation_points == 45.0
    assert settings.trailing_stop_distance_points == 15.0


@pytest.mark.parametrize(
    "env_name",
    [
        ACTIVATION_ENV,
        DISTANCE_ENV,
    ],
)
@pytest.mark.parametrize(
    "invalid_value",
    [
        "0",
        "-0.01",
        "nan",
        "inf",
        "not-a-number",
        "",
        "   ",
    ],
)
def test_invalid_trailing_stop_policy_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    env_name: str,
    invalid_value: str,
) -> None:
    _configure_required_base_env(monkeypatch)

    monkeypatch.delenv(
        ACTIVATION_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        DISTANCE_ENV,
        raising=False,
    )

    monkeypatch.setenv(
        env_name,
        invalid_value,
    )

    with pytest.raises(ValueError):
        APISettings()


def test_trailing_stop_policy_values_are_finite_and_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_required_base_env(monkeypatch)

    monkeypatch.setenv(
        ACTIVATION_ENV,
        "45.0",
    )
    monkeypatch.setenv(
        DISTANCE_ENV,
        "15.0",
    )

    settings = APISettings()

    values = (
        settings.trailing_stop_activation_points,
        settings.trailing_stop_distance_points,
    )

    assert all(
        math.isfinite(value) and value > 0.0
        for value in values
    )
