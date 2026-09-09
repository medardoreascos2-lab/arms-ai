from __future__ import annotations

import ast
import math
import os
from pathlib import Path

import pytest

from backend.config.api_settings import APISettings


MINIMUM_READY_FIELD = (
    "multi_timeframe_minimum_ready_weight"
)
NEUTRAL_FIELD = (
    "multi_timeframe_neutral_threshold"
)
CONFLICT_FIELD = (
    "multi_timeframe_conflict_weight_threshold"
)
DOMINANCE_FIELD = (
    "multi_timeframe_dominance_margin"
)

MINIMUM_READY_ENV = (
    "ARMS_MULTI_TIMEFRAME_MINIMUM_READY_WEIGHT"
)
NEUTRAL_ENV = (
    "ARMS_MULTI_TIMEFRAME_NEUTRAL_THRESHOLD"
)
CONFLICT_ENV = (
    "ARMS_MULTI_TIMEFRAME_CONFLICT_WEIGHT_THRESHOLD"
)
DOMINANCE_ENV = (
    "ARMS_MULTI_TIMEFRAME_DOMINANCE_MARGIN"
)

TARGET_ENVS = (
    MINIMUM_READY_ENV,
    NEUTRAL_ENV,
    CONFLICT_ENV,
    DOMINANCE_ENV,
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


def _multi_timeframe_call() -> ast.Call:
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

        if name == "MultiTimeframeDecisionEngineV2":
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
        (MINIMUM_READY_FIELD, 0.65),
        (NEUTRAL_FIELD, 0.15),
        (CONFLICT_FIELD, 0.25),
        (DOMINANCE_FIELD, 0.35),
    ),
)
def test_multi_timeframe_policy_defaults_are_canonical(
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
            MINIMUM_READY_ENV,
            MINIMUM_READY_FIELD,
            "0.70",
        ),
        (
            NEUTRAL_ENV,
            NEUTRAL_FIELD,
            "0.20",
        ),
        (
            CONFLICT_ENV,
            CONFLICT_FIELD,
            "0.30",
        ),
        (
            DOMINANCE_ENV,
            DOMINANCE_FIELD,
            "0.40",
        ),
    ),
)
def test_multi_timeframe_policy_env_overrides_are_canonical(
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

    assert float(
        getattr(
            settings,
            field_name,
        )
    ) == pytest.approx(
        float(value)
    )


@pytest.mark.parametrize(
    "invalid_value",
    (
        "0",
        "-0.01",
        "1.01",
        "nan",
        "inf",
        "-inf",
        "",
        " ",
        "text",
    ),
)
def test_multi_timeframe_minimum_ready_weight_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: str,
) -> None:
    _prepare_env(
        monkeypatch,
        **{
            MINIMUM_READY_ENV: invalid_value,
        },
    )

    with pytest.raises(
        (TypeError, ValueError)
    ):
        APISettings()


@pytest.mark.parametrize(
    ("environment_name", "invalid_value"),
    (
        (NEUTRAL_ENV, "-0.01"),
        (NEUTRAL_ENV, "1.01"),
        (NEUTRAL_ENV, "nan"),
        (NEUTRAL_ENV, "inf"),
        (NEUTRAL_ENV, "-inf"),
        (NEUTRAL_ENV, ""),
        (NEUTRAL_ENV, " "),
        (NEUTRAL_ENV, "text"),
        (CONFLICT_ENV, "-0.01"),
        (CONFLICT_ENV, "1.01"),
        (CONFLICT_ENV, "nan"),
        (CONFLICT_ENV, "inf"),
        (CONFLICT_ENV, "-inf"),
        (CONFLICT_ENV, ""),
        (CONFLICT_ENV, " "),
        (CONFLICT_ENV, "text"),
        (DOMINANCE_ENV, "-0.01"),
        (DOMINANCE_ENV, "1.01"),
        (DOMINANCE_ENV, "nan"),
        (DOMINANCE_ENV, "inf"),
        (DOMINANCE_ENV, "-inf"),
        (DOMINANCE_ENV, ""),
        (DOMINANCE_ENV, " "),
        (DOMINANCE_ENV, "text"),
    ),
)
def test_multi_timeframe_zero_allowed_ratios_reject_invalid_values(
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

    with pytest.raises(
        (TypeError, ValueError)
    ):
        APISettings()


@pytest.mark.parametrize(
    ("environment_name", "field_name"),
    (
        (
            NEUTRAL_ENV,
            NEUTRAL_FIELD,
        ),
        (
            CONFLICT_ENV,
            CONFLICT_FIELD,
        ),
        (
            DOMINANCE_ENV,
            DOMINANCE_FIELD,
        ),
    ),
)
def test_multi_timeframe_zero_allowed_ratios_accept_zero(
    monkeypatch: pytest.MonkeyPatch,
    environment_name: str,
    field_name: str,
) -> None:
    settings = _settings(
        monkeypatch,
        **{
            environment_name: "0",
        },
    )

    assert math.isclose(
        float(
            getattr(
                settings,
                field_name,
            )
        ),
        0.0,
    )


def test_multi_timeframe_minimum_ready_weight_accepts_upper_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        **{
            MINIMUM_READY_ENV: "1",
        },
    )

    assert math.isclose(
        float(
            getattr(
                settings,
                MINIMUM_READY_FIELD,
            )
        ),
        1.0,
    )


@pytest.mark.parametrize(
    ("environment_name", "field_name"),
    (
        (
            NEUTRAL_ENV,
            NEUTRAL_FIELD,
        ),
        (
            CONFLICT_ENV,
            CONFLICT_FIELD,
        ),
        (
            DOMINANCE_ENV,
            DOMINANCE_FIELD,
        ),
    ),
)
def test_multi_timeframe_zero_allowed_ratios_accept_upper_boundary(
    monkeypatch: pytest.MonkeyPatch,
    environment_name: str,
    field_name: str,
) -> None:
    settings = _settings(
        monkeypatch,
        **{
            environment_name: "1",
        },
    )

    assert math.isclose(
        float(
            getattr(
                settings,
                field_name,
            )
        ),
        1.0,
    )


@pytest.mark.parametrize(
    ("keyword_name", "settings_expression"),
    (
        (
            "minimum_ready_weight",
            "settings.multi_timeframe_minimum_ready_weight",
        ),
        (
            "neutral_threshold",
            "settings.multi_timeframe_neutral_threshold",
        ),
        (
            "conflict_weight_threshold",
            "settings.multi_timeframe_conflict_weight_threshold",
        ),
        (
            "dominance_margin",
            "settings.multi_timeframe_dominance_margin",
        ),
    ),
)
def test_multi_timeframe_engine_app_wiring_uses_canonical_settings(
    keyword_name: str,
    settings_expression: str,
) -> None:
    values = _keyword_map(
        _multi_timeframe_call()
    )

    assert values[
        keyword_name
    ] == settings_expression


def test_multi_timeframe_policy_fields_are_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        **{
            MINIMUM_READY_ENV: "0.70",
            NEUTRAL_ENV: "0.20",
            CONFLICT_ENV: "0.30",
            DOMINANCE_ENV: "0.40",
        },
    )

    assert getattr(
        settings,
        MINIMUM_READY_FIELD,
    ) == pytest.approx(0.70)

    assert getattr(
        settings,
        NEUTRAL_FIELD,
    ) == pytest.approx(0.20)

    assert getattr(
        settings,
        CONFLICT_FIELD,
    ) == pytest.approx(0.30)

    assert getattr(
        settings,
        DOMINANCE_FIELD,
    ) == pytest.approx(0.40)


def test_existing_multi_timeframe_engine_defaults_remain_parameterized(
) -> None:
    path = Path(
        "backend/intelligence/"
        "multi_timeframe_decision_engine_v2.py"
    )
    source = path.read_text(
        encoding="utf-8",
        errors="strict",
    )

    assert "minimum_ready_weight: float = 0.65" in source
    assert "neutral_threshold: float = 0.15" in source
    assert "conflict_weight_threshold: float = 0.25" in source
    assert "dominance_margin: float = 0.35" in source
