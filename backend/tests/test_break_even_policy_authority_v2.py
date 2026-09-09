from __future__ import annotations

import ast
import math
import os
from pathlib import Path

import pytest

from backend.config.api_settings import APISettings
from backend.execution.break_even_engine_v2 import (
    BreakEvenEngineV2,
)


TRIGGER_FIELD = "break_even_trigger_profit_points"
OFFSET_FIELD = "break_even_offset_points"

TRIGGER_ENV = "ARMS_BREAK_EVEN_TRIGGER_PROFIT_POINTS"
OFFSET_ENV = "ARMS_BREAK_EVEN_OFFSET_POINTS"


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
    "ARMS_SIGNAL_EXECUTION_COOLDOWN_MINUTES": "15",
}


def _prepare_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    trigger: str | None = None,
    offset: str | None = None,
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

    monkeypatch.delenv(
        TRIGGER_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        OFFSET_ENV,
        raising=False,
    )

    if trigger is not None:
        monkeypatch.setenv(
            TRIGGER_ENV,
            trigger,
        )

    if offset is not None:
        monkeypatch.setenv(
            OFFSET_ENV,
            offset,
        )


def _settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    trigger: str | None = None,
    offset: str | None = None,
) -> APISettings:
    _prepare_env(
        monkeypatch,
        trigger=trigger,
        offset=offset,
    )

    return APISettings()


def _break_even_engine_call() -> ast.Call:
    path = Path(
        "backend/api/app.py"
    )

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

        if name == "BreakEvenEngineV2":
            calls.append(node)

    assert len(calls) == 1

    return calls[0]


def test_break_even_policy_defaults_are_canonical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
    )

    assert getattr(
        settings,
        TRIGGER_FIELD,
    ) == 15.0

    assert getattr(
        settings,
        OFFSET_FIELD,
    ) == 1.0


def test_break_even_policy_env_overrides_are_canonical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        trigger="22.5",
        offset="2.25",
    )

    assert getattr(
        settings,
        TRIGGER_FIELD,
    ) == 22.5

    assert getattr(
        settings,
        OFFSET_FIELD,
    ) == 2.25


@pytest.mark.parametrize(
    "invalid_value",
    (
        "0",
        "-1",
        "-0.1",
        "nan",
        "NaN",
        "inf",
        "+inf",
        "-inf",
        "",
        " ",
        "text",
    ),
)
def test_break_even_trigger_rejects_invalid_external_policy(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: str,
) -> None:
    _prepare_env(
        monkeypatch,
        trigger=invalid_value,
        offset="1",
    )

    with pytest.raises(
        (TypeError, ValueError)
    ):
        APISettings()


@pytest.mark.parametrize(
    "valid_value",
    (
        "0.1",
        "1",
        "15",
        "22.5",
        "100",
    ),
)
def test_break_even_trigger_accepts_positive_finite_policy(
    monkeypatch: pytest.MonkeyPatch,
    valid_value: str,
) -> None:
    settings = _settings(
        monkeypatch,
        trigger=valid_value,
        offset="1",
    )

    value = getattr(
        settings,
        TRIGGER_FIELD,
    )

    assert value == float(valid_value)
    assert math.isfinite(value)
    assert value > 0


@pytest.mark.parametrize(
    "invalid_value",
    (
        "-1",
        "-0.1",
        "nan",
        "NaN",
        "inf",
        "+inf",
        "-inf",
        "",
        " ",
        "text",
    ),
)
def test_break_even_offset_rejects_invalid_external_policy(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: str,
) -> None:
    _prepare_env(
        monkeypatch,
        trigger="15",
        offset=invalid_value,
    )

    with pytest.raises(
        (TypeError, ValueError)
    ):
        APISettings()


@pytest.mark.parametrize(
    "valid_value",
    (
        "0",
        "0.1",
        "1",
        "2.5",
        "100",
    ),
)
def test_break_even_offset_accepts_nonnegative_finite_policy(
    monkeypatch: pytest.MonkeyPatch,
    valid_value: str,
) -> None:
    settings = _settings(
        monkeypatch,
        trigger="15",
        offset=valid_value,
    )

    value = getattr(
        settings,
        OFFSET_FIELD,
    )

    assert value == float(valid_value)
    assert math.isfinite(value)
    assert value >= 0


def test_break_even_app_wiring_uses_canonical_settings(
) -> None:
    call = _break_even_engine_call()

    values = {
        keyword.arg: ast.unparse(
            keyword.value
        )
        for keyword in call.keywords
        if keyword.arg is not None
    }

    assert values[
        "trigger_profit_points"
    ] == (
        "settings."
        "break_even_trigger_profit_points"
    )

    assert values[
        "offset_points"
    ] == (
        "settings."
        "break_even_offset_points"
    )


def test_break_even_engine_remains_parameterized(
) -> None:
    path = Path(
        "backend/execution/"
        "break_even_engine_v2.py"
    )

    source = path.read_text(
        encoding="utf-8",
        errors="strict",
    )

    assert (
        "trigger_profit_points: float"
        in source
    )

    assert (
        "offset_points: float"
        in source
    )

    assert (
        "trigger_profit_points: float ="
        not in source
    )

    assert (
        "offset_points: float ="
        not in source
    )


def test_break_even_engine_runtime_semantics_remain_unchanged(
) -> None:
    engine = BreakEvenEngineV2(
        trigger_profit_points=15.0,
        offset_points=1.0,
    )

    assert engine.trigger_profit_points == 15.0
    assert engine.offset_points == 1.0

    assert (
        engine.apply(
            position={
                "direction": "LONG",
                "status": "OPEN",
                "entry_price": 100.0,
                "stop_loss": 90.0,
            },
            current_price=114.0,
        )["status"]
        == "WAITING"
    )

    result = engine.apply(
        position={
            "direction": "LONG",
            "status": "OPEN",
            "entry_price": 100.0,
            "stop_loss": 90.0,
        },
        current_price=115.0,
    )

    assert result["status"] == "BREAK_EVEN_ACTIVE"
    assert result["new_stop_loss"] == 101.0
