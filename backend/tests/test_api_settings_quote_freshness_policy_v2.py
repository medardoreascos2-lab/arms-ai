from __future__ import annotations

import math

import pytest

from backend.config.api_settings import APISettings


_ENV = "ARMS_MAXIMUM_QUOTE_AGE_SECONDS"


def test_quote_freshness_policy_requires_explicit_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        _ENV,
        raising=False,
    )

    with pytest.raises(
        ValueError,
        match="ARMS_MAXIMUM_QUOTE_AGE_SECONDS",
    ):
        APISettings()


@pytest.mark.parametrize(
    "raw_value",
    [
        "",
        " ",
        "abc",
        "nan",
        "NaN",
        "inf",
        "+inf",
        "-inf",
        "0",
        "0.0",
        "-1",
    ],
)
def test_quote_freshness_policy_rejects_invalid_environment(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
) -> None:
    monkeypatch.setenv(
        _ENV,
        raw_value,
    )

    with pytest.raises(
        ValueError,
        match="ARMS_MAXIMUM_QUOTE_AGE_SECONDS",
    ):
        APISettings()


@pytest.mark.parametrize(
    "raw_value",
    [
        "0.001",
        "0.25",
        "1",
        "5.0",
        "30",
    ],
)
def test_quote_freshness_policy_accepts_explicit_finite_positive_value(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
) -> None:
    monkeypatch.setenv(
        _ENV,
        raw_value,
    )

    settings = APISettings()

    assert settings.maximum_quote_age_seconds == pytest.approx(
        float(raw_value)
    )

    assert math.isfinite(
        settings.maximum_quote_age_seconds
    )

    assert settings.maximum_quote_age_seconds > 0.0


def test_quote_freshness_policy_has_no_static_five_second_default() -> None:
    from pathlib import Path

    source = Path(
        "backend/config/api_settings.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        '"ARMS_MAXIMUM_QUOTE_AGE_SECONDS",'
        '\n                "5.0",'
    ) not in source

    assert (
        "'ARMS_MAXIMUM_QUOTE_AGE_SECONDS',"
        "\n                '5.0',"
    ) not in source
