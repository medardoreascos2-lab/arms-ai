from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from backend.config.api_settings import APISettings


APP_PATH = Path("backend/api/app.py")
SETTINGS_PATH = Path(
    "backend/config/api_settings.py"
)

FIELD_NAME = "paper_execution_slippage_points"
ENV_NAME = "ARMS_PAPER_EXECUTION_SLIPPAGE_POINTS"

DEFAULT_SLIPPAGE = 0.25
CUSTOM_SLIPPAGE = 0.75


def _paper_execution_slippage_sources() -> list[str]:
    source = APP_PATH.read_text(
        encoding="utf-8",
        errors="strict",
    )

    tree = ast.parse(source)

    values: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            continue

        if name != "PaperExecutionEngineV2":
            continue

        for keyword in node.keywords:
            if keyword.arg == "slippage_points":
                values.append(
                    ast.unparse(keyword.value)
                )

    return values


def _clear_slippage_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        ENV_NAME,
        raising=False,
    )


def test_api_settings_exposes_canonical_paper_execution_slippage() -> None:
    settings = APISettings()

    assert hasattr(
        settings,
        FIELD_NAME,
    )


def test_settings_source_declares_canonical_slippage_env() -> None:
    source = SETTINGS_PATH.read_text(
        encoding="utf-8",
        errors="strict",
    )

    assert FIELD_NAME in source
    assert ENV_NAME in source


def test_default_slippage_preserves_current_production_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_slippage_env(monkeypatch)

    settings = APISettings()

    assert (
        settings.paper_execution_slippage_points
        == DEFAULT_SLIPPAGE
    )


def test_custom_slippage_env_controls_canonical_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        ENV_NAME,
        str(CUSTOM_SLIPPAGE),
    )

    settings = APISettings()

    assert (
        settings.paper_execution_slippage_points
        == CUSTOM_SLIPPAGE
    )


@pytest.mark.parametrize(
    "value",
    [
        "-0.01",
        "-1",
        "nan",
        "NaN",
        "inf",
        "+inf",
        "-inf",
        "Infinity",
        "-Infinity",
        "",
        " ",
        "abc",
    ],
)
def test_invalid_slippage_env_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv(
        ENV_NAME,
        value,
    )

    with pytest.raises(
        (TypeError, ValueError),
    ):
        APISettings()


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "0.0",
        "0.25",
        "1.5",
    ],
)
def test_valid_non_negative_finite_slippage_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv(
        ENV_NAME,
        value,
    )

    settings = APISettings()

    resolved = (
        settings.paper_execution_slippage_points
    )

    assert math.isfinite(resolved)
    assert resolved >= 0.0
    assert resolved == float(value)


def test_production_app_uses_canonical_slippage_authority() -> None:
    sources = _paper_execution_slippage_sources()

    assert sources == [
        "settings.paper_execution_slippage_points"
    ]


def test_production_app_no_longer_owns_literal_slippage_policy() -> None:
    sources = _paper_execution_slippage_sources()

    assert "0.25" not in sources


def test_slippage_authority_remains_semantically_independent() -> None:
    source = SETTINGS_PATH.read_text(
        encoding="utf-8",
        errors="strict",
    )

    assert FIELD_NAME in source

    forbidden_derivations = [
        "maximum_spread_points",
        "maximum_stop_points",
        "minimum_atr_points",
        "risk_per_trade",
        "minimum_reward_risk_ratio",
        "trailing_stop_distance_points",
        "trailing_stop_activation_points",
    ]

    field_position = source.find(FIELD_NAME)

    assert field_position >= 0

    window = source[
        field_position:
        field_position + 1200
    ]

    for forbidden in forbidden_derivations:
        assert forbidden not in window
