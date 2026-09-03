from __future__ import annotations

import ast
from pathlib import Path


SERVICE_FILE = Path(
    "backend/services/live_market_analysis_service.py"
)


def _source() -> str:
    return SERVICE_FILE.read_text(
        encoding="utf-8"
    )


def _tree() -> ast.Module:
    return ast.parse(
        _source()
    )


def _method(
    name: str,
) -> ast.FunctionDef:
    tree = _tree()

    matches = [
        child
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        for child in node.body
        if (
            isinstance(child, ast.FunctionDef)
            and child.name == name
        )
    ]

    assert len(matches) == 1

    return matches[0]


def test_single_volume_quality_authority_exists(
) -> None:
    tree = _tree()

    helpers = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.FunctionDef)
            and node.name
            == "_calculate_volume_quality_score"
        )
    ]

    assert len(helpers) == 1


def test_analyze_probability_volume_uses_canonical_helper(
) -> None:
    source = _source()
    analyze = _method(
        "analyze"
    )

    assignments = []

    for node in ast.walk(analyze):
        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        if len(node.targets) != 1:
            continue

        target = node.targets[0]

        if not (
            isinstance(target, ast.Name)
            and target.id == "volume_score"
        ):
            continue

        segment = ast.get_source_segment(
            source,
            node,
        )

        assignments.append(
            (
                node,
                segment,
            )
        )

    assert len(assignments) == 1

    assignment, segment = assignments[0]

    assert segment is not None

    assert (
        "_calculate_volume_quality_score"
        in segment
    )

    assert "candles" in segment

    assert not isinstance(
        assignment.value,
        ast.IfExp,
    )


def test_probability_receives_canonical_volume_score(
) -> None:
    source = _source()
    analyze = _method(
        "analyze"
    )

    calls = []

    for node in ast.walk(analyze):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        segment = ast.get_source_segment(
            source,
            node,
        )

        if (
            segment
            and
            "probability_engine_v2.evaluate"
            in segment
        ):
            calls.append(node)

    assert len(calls) == 1

    call = calls[0]

    volume_keywords = [
        keyword
        for keyword in call.keywords
        if keyword.arg == "volume_score"
    ]

    assert len(volume_keywords) == 1

    value = volume_keywords[0].value

    assert isinstance(
        value,
        ast.Name,
    )

    assert value.id == "volume_score"


def test_boolean_volume_adapter_is_absent(
) -> None:
    source = _source()
    analyze = _method(
        "analyze"
    )

    boolean_adapters = []

    for node in ast.walk(analyze):
        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        if len(node.targets) != 1:
            continue

        target = node.targets[0]

        if (
            isinstance(target, ast.Name)
            and target.id == "volume_score"
            and isinstance(
                node.value,
                ast.IfExp,
            )
        ):
            boolean_adapters.append(
                ast.get_source_segment(
                    source,
                    node,
                )
            )

    assert boolean_adapters == []
