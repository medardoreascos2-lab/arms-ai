from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.config.api_settings import APISettings


APP_PATH = Path("backend/api/app.py")
SETTINGS_PATH = Path("backend/config/api_settings.py")


def _source(path: Path) -> str:
    return path.read_text(
        encoding="utf-8"
    )


def _calls_named(
    source: str,
    name: str,
) -> list[ast.Call]:
    tree = ast.parse(source)

    calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        try:
            called_name = ast.unparse(
                node.func
            ).split(".")[-1]
        except Exception:
            continue

        if called_name == name:
            calls.append(
                node
            )

    return calls


def _keyword_expression(
    call: ast.Call,
    keyword_name: str,
) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == keyword_name:
            return ast.unparse(
                keyword.value
            )

    return None


def test_api_settings_owns_maximum_open_positions_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ARMS_MAXIMUM_OPEN_POSITIONS",
        "3",
    )

    settings = APISettings()

    assert settings.maximum_open_positions == 3


def test_maximum_open_positions_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ARMS_MAXIMUM_OPEN_POSITIONS",
        "0",
    )

    with pytest.raises(
        ValueError,
    ):
        APISettings()


def test_account_risk_guard_uses_settings_authority() -> None:
    source = _source(
        APP_PATH
    )

    calls = _calls_named(
        source,
        "AccountRiskGuard",
    )

    assert len(calls) == 1

    expression = _keyword_expression(
        calls[0],
        "max_open_positions",
    )

    assert expression == (
        "settings.maximum_open_positions"
    )


def test_live_risk_manager_uses_settings_authority() -> None:
    source = _source(
        APP_PATH
    )

    calls = _calls_named(
        source,
        "RiskManagerV2",
    )

    matching = []

    for call in calls:
        expression = _keyword_expression(
            call,
            "maximum_open_positions",
        )

        if expression is not None:
            matching.append(
                expression
            )

    assert (
        "settings.maximum_open_positions"
        in matching
    )


def test_app_has_no_literal_maximum_open_positions_authority() -> None:
    source = _source(
        APP_PATH
    )

    tree = ast.parse(
        source
    )

    literal_authorities = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        for keyword in node.keywords:
            if keyword.arg not in {
                "max_open_positions",
                "maximum_open_positions",
            }:
                continue

            if (
                isinstance(
                    keyword.value,
                    ast.Constant,
                )
                and isinstance(
                    keyword.value.value,
                    int,
                )
            ):
                literal_authorities.append(
                    (
                        getattr(
                            node,
                            "lineno",
                            None,
                        ),
                        keyword.arg,
                        keyword.value.value,
                    )
                )

    assert literal_authorities == []


def test_settings_source_declares_maximum_open_positions() -> None:
    source = _source(
        SETTINGS_PATH
    )

    assert "maximum_open_positions" in source
    assert "ARMS_MAXIMUM_OPEN_POSITIONS" in source
