from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

APP_PATH = ROOT / "backend/api/app.py"
SETTINGS_PATH = ROOT / "backend/config/api_settings.py"

SETTING_NAME = "minimum_execution_confidence"


def _parse(path: Path) -> tuple[str, ast.Module]:
    source = path.read_text(
        encoding="utf-8",
        errors="strict",
    )
    return source, ast.parse(source)


def _assignment_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.Assign):
            targets = node.targets
        else:
            continue

        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, ast.Attribute):
                names.add(target.attr)

    return names


def _execution_decision_calls(
    source: str,
    tree: ast.AST,
) -> list[ast.Call]:
    calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        name = None

        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr

        if name == "ExecutionDecisionEngine":
            calls.append(node)

    return calls


def test_legacy_confidence_has_explicit_settings_authority() -> None:
    _, settings_tree = _parse(SETTINGS_PATH)

    names = _assignment_names(settings_tree)

    assert SETTING_NAME in names, (
        "GAP #2Y: legacy ExecutionDecisionEngine minimum_confidence "
        "must have its own explicit canonical settings authority."
    )


def test_app_does_not_construct_legacy_engine_with_literal_confidence() -> None:
    source, tree = _parse(APP_PATH)

    calls = _execution_decision_calls(
        source,
        tree,
    )

    assert len(calls) == 1

    call = calls[0]

    minimum_confidence = next(
        (
            keyword.value
            for keyword in call.keywords
            if keyword.arg == "minimum_confidence"
        ),
        None,
    )

    assert minimum_confidence is not None

    assert not isinstance(
        minimum_confidence,
        ast.Constant,
    ), (
        "GAP #2Y: production legacy ExecutionDecisionEngine "
        "still owns a literal minimum_confidence."
    )


def test_app_uses_legacy_confidence_settings_authority() -> None:
    source, tree = _parse(APP_PATH)

    calls = _execution_decision_calls(
        source,
        tree,
    )

    assert len(calls) == 1

    call = calls[0]

    minimum_confidence = next(
        (
            keyword.value
            for keyword in call.keywords
            if keyword.arg == "minimum_confidence"
        ),
        None,
    )

    assert minimum_confidence is not None

    expression = ast.get_source_segment(
        source,
        minimum_confidence,
    )

    assert expression is not None

    assert SETTING_NAME in expression, (
        "GAP #2Y: production legacy ExecutionDecisionEngine "
        "must consume the canonical legacy confidence authority."
    )


def test_a_plus_authorities_remain_semantically_separate() -> None:
    source, tree = _parse(APP_PATH)

    legacy_calls = _execution_decision_calls(
        source,
        tree,
    )

    assert len(legacy_calls) == 1

    legacy_call = legacy_calls[0]

    minimum_confidence = next(
        (
            keyword.value
            for keyword in legacy_call.keywords
            if keyword.arg == "minimum_confidence"
        ),
        None,
    )

    assert minimum_confidence is not None

    expression = ast.get_source_segment(
        source,
        minimum_confidence,
    )

    assert expression is not None

    assert "minimum_a_plus_probability" not in expression
    assert "minimum_a_plus_confluence_score" not in expression
