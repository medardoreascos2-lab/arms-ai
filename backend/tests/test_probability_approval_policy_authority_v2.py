from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.api.app import create_app
from backend.config.api_settings import APISettings


ROOT = Path(__file__).resolve().parents[2]

APP_PATH = ROOT / "backend/api/app.py"
SETTINGS_PATH = ROOT / "backend/config/api_settings.py"

ENV_NAME = "ARMS_MINIMUM_PROBABILITY_APPROVAL"


def _assignment_names(node: ast.AST) -> set[str]:
    names: set[str] = set()

    if isinstance(node, ast.AnnAssign):
        targets = [node.target]
    elif isinstance(node, ast.Assign):
        targets = list(node.targets)
    else:
        return names

    for target in targets:
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute):
            names.add(target.attr)

    return names


def _probability_engine_calls() -> list[ast.Call]:
    tree = ast.parse(
        APP_PATH.read_text(
            encoding="utf-8",
            errors="strict",
        )
    )

    calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        function = node.func

        if (
            isinstance(function, ast.Name)
            and function.id == "ProbabilityEngineV2"
        ):
            calls.append(node)

        elif (
            isinstance(function, ast.Attribute)
            and function.attr == "ProbabilityEngineV2"
        ):
            calls.append(node)

    return calls


def test_probability_approval_has_independent_settings_authority() -> None:
    source = SETTINGS_PATH.read_text(
        encoding="utf-8",
        errors="strict",
    )
    tree = ast.parse(source)

    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(
            node,
            (ast.AnnAssign, ast.Assign),
        )
        and (
            "minimum_probability_approval"
            in _assignment_names(node)
        )
    ]

    assert len(assignments) == 1
    assert ENV_NAME in source


def test_probability_approval_authority_is_semantically_independent() -> None:
    source = SETTINGS_PATH.read_text(
        encoding="utf-8",
        errors="strict",
    )

    assert "minimum_a_plus_probability" in source
    assert "minimum_probability_approval" in source

    assert (
        "minimum_probability_approval"
        != "minimum_a_plus_probability"
    )


def test_production_probability_engine_consumes_authority() -> None:
    calls = _probability_engine_calls()

    assert len(calls) == 1

    keyword_values = {
        keyword.arg: ast.unparse(keyword.value)
        for keyword in calls[0].keywords
        if keyword.arg is not None
    }

    assert (
        keyword_values.get(
            "minimum_approval_probability"
        )
        == "settings.minimum_probability_approval"
    )


def test_production_literal_is_removed() -> None:
    calls = _probability_engine_calls()

    assert len(calls) == 1

    keyword_values = {
        keyword.arg: ast.unparse(keyword.value)
        for keyword in calls[0].keywords
        if keyword.arg is not None
    }

    assert (
        keyword_values.get(
            "minimum_approval_probability"
        )
        != "0.8"
    )


def test_default_probability_approval_preserves_current_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        ENV_NAME,
        raising=False,
    )

    settings = APISettings()

    assert (
        settings.minimum_probability_approval
        == pytest.approx(0.80)
    )


def test_custom_probability_approval_reaches_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        ENV_NAME,
        "0.83",
    )

    settings = APISettings()

    assert (
        settings.minimum_probability_approval
        == pytest.approx(0.83)
    )

    app = create_app(settings=settings)

    assert (
        app.state
        .probability_engine_v2
        .minimum_approval_probability
        == pytest.approx(0.83)
    )


@pytest.mark.parametrize(
    "value",
    [
        "-0.01",
        "1.01",
        "nan",
        "inf",
        "not-a-number",
        "",
        "   ",
    ],
)
def test_probability_approval_rejects_invalid_environment_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv(
        ENV_NAME,
        value,
    )

    with pytest.raises(ValueError):
        APISettings()
