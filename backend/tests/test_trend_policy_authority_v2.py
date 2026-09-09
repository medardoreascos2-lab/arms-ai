from __future__ import annotations

import ast
import math
import os
from pathlib import Path

import pytest

from backend.config.api_settings import APISettings


FAST_FIELD = "trend_fast_period"
SLOW_FIELD = "trend_slow_period"
SLOPE_FIELD = "trend_slope_lookback"
SIDEWAYS_FIELD = "trend_sideways_threshold_percent"

FAST_ENV = "ARMS_TREND_FAST_PERIOD"
SLOW_ENV = "ARMS_TREND_SLOW_PERIOD"
SLOPE_ENV = "ARMS_TREND_SLOPE_LOOKBACK"
SIDEWAYS_ENV = "ARMS_TREND_SIDEWAYS_THRESHOLD_PERCENT"

TARGET_ENVS = (
    FAST_ENV,
    SLOW_ENV,
    SLOPE_ENV,
    SIDEWAYS_ENV,
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


def _trend_engine_call() -> ast.Call:
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

        if name == "TrendEngineV2":
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
        (FAST_FIELD, 10),
        (SLOW_FIELD, 50),
        (SLOPE_FIELD, 5),
        (SIDEWAYS_FIELD, 0.0005),
    ),
)
def test_trend_policy_defaults_are_canonical(
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
            FAST_ENV,
            FAST_FIELD,
            "12",
        ),
        (
            SLOW_ENV,
            SLOW_FIELD,
            "60",
        ),
        (
            SLOPE_ENV,
            SLOPE_FIELD,
            "7",
        ),
        (
            SIDEWAYS_ENV,
            SIDEWAYS_FIELD,
            "0.001",
        ),
    ),
)
def test_trend_policy_env_overrides_are_canonical(
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
        "1",
        "0",
        "-1",
        "",
        " ",
        "1.5",
        "text",
    ),
)
def test_trend_fast_period_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: str,
) -> None:
    _prepare_env(
        monkeypatch,
        **{
            FAST_ENV: invalid_value,
        },
    )

    with pytest.raises(
        (TypeError, ValueError)
    ):
        APISettings()


@pytest.mark.parametrize(
    "invalid_value",
    (
        "1",
        "0",
        "-1",
        "",
        " ",
        "1.5",
        "text",
    ),
)
def test_trend_slow_period_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: str,
) -> None:
    _prepare_env(
        monkeypatch,
        **{
            SLOW_ENV: invalid_value,
        },
    )

    with pytest.raises(
        (TypeError, ValueError)
    ):
        APISettings()


@pytest.mark.parametrize(
    "invalid_value",
    (
        "1",
        "0",
        "-1",
        "",
        " ",
        "1.5",
        "text",
    ),
)
def test_trend_slope_lookback_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: str,
) -> None:
    _prepare_env(
        monkeypatch,
        **{
            SLOPE_ENV: invalid_value,
        },
    )

    with pytest.raises(
        (TypeError, ValueError)
    ):
        APISettings()


@pytest.mark.parametrize(
    "invalid_value",
    (
        "0",
        "-0.001",
        "nan",
        "inf",
        "-inf",
        "",
        " ",
        "text",
    ),
)
def test_trend_sideways_threshold_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: str,
) -> None:
    _prepare_env(
        monkeypatch,
        **{
            SIDEWAYS_ENV: invalid_value,
        },
    )

    with pytest.raises(
        (TypeError, ValueError)
    ):
        APISettings()


@pytest.mark.parametrize(
    ("fast", "slow"),
    (
        ("10", "10"),
        ("20", "10"),
        ("50", "49"),
    ),
)
def test_trend_policy_rejects_slow_not_greater_than_fast(
    monkeypatch: pytest.MonkeyPatch,
    fast: str,
    slow: str,
) -> None:
    _prepare_env(
        monkeypatch,
        **{
            FAST_ENV: fast,
            SLOW_ENV: slow,
        },
    )

    with pytest.raises(ValueError):
        APISettings()


def test_trend_policy_accepts_valid_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        **{
            FAST_ENV: "2",
            SLOW_ENV: "3",
            SLOPE_ENV: "2",
            SIDEWAYS_ENV: "0.000001",
        },
    )

    assert getattr(
        settings,
        FAST_FIELD,
    ) == 2

    assert getattr(
        settings,
        SLOW_FIELD,
    ) == 3

    assert getattr(
        settings,
        SLOPE_FIELD,
    ) == 2

    assert math.isclose(
        float(
            getattr(
                settings,
                SIDEWAYS_FIELD,
            )
        ),
        0.000001,
    )


@pytest.mark.parametrize(
    ("keyword_name", "settings_expression"),
    (
        (
            "fast_period",
            "settings.trend_fast_period",
        ),
        (
            "slow_period",
            "settings.trend_slow_period",
        ),
        (
            "slope_lookback",
            "settings.trend_slope_lookback",
        ),
        (
            "sideways_threshold_percent",
            "settings.trend_sideways_threshold_percent",
        ),
    ),
)
def test_trend_engine_app_wiring_uses_canonical_settings(
    keyword_name: str,
    settings_expression: str,
) -> None:
    values = _keyword_map(
        _trend_engine_call()
    )

    assert values[
        keyword_name
    ] == settings_expression


def test_trend_policy_fields_are_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        **{
            FAST_ENV: "12",
            SLOW_ENV: "60",
            SLOPE_ENV: "7",
            SIDEWAYS_ENV: "0.001",
        },
    )

    assert getattr(
        settings,
        FAST_FIELD,
    ) == 12

    assert getattr(
        settings,
        SLOW_FIELD,
    ) == 60

    assert getattr(
        settings,
        SLOPE_FIELD,
    ) == 7

    assert getattr(
        settings,
        SIDEWAYS_FIELD,
    ) == pytest.approx(0.001)


def test_market_regime_trend_policy_remains_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)

    assert hasattr(
        settings,
        "market_regime_trend_threshold",
    )

    assert FAST_FIELD != "market_regime_trend_threshold"
    assert SLOW_FIELD != "market_regime_trend_threshold"
    assert SLOPE_FIELD != "market_regime_trend_threshold"
    assert SIDEWAYS_FIELD != "market_regime_trend_threshold"
