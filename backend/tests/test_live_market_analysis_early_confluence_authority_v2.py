from pathlib import Path
import ast


LIVE_FILE = Path(
    "backend/services/live_market_analysis_service.py"
)


def _tree() -> ast.AST:
    return ast.parse(
        LIVE_FILE.read_text(encoding="utf-8")
    )


def _confluence_calls() -> list[ast.Call]:
    calls: list[ast.Call] = []

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue

        try:
            name = ast.unparse(node.func)
        except Exception:
            continue

        if name == "self._evaluate_confluence_v2":
            calls.append(node)

    return sorted(
        calls,
        key=lambda node: node.lineno,
    )


def _authority_assignments(
    name: str,
) -> list[int]:
    lines: list[int] = []

    for node in ast.walk(_tree()):
        if not isinstance(
            node,
            (ast.Assign, ast.AnnAssign),
        ):
            continue

        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
        )

        for target in targets:
            if (
                isinstance(target, ast.Name)
                and target.id == name
            ):
                lines.append(node.lineno)

    return sorted(lines)


def _keyword_value(
    call: ast.Call,
    name: str,
) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return ast.unparse(keyword.value)

    return None


def _result_assignment_lines() -> list[int]:
    lines: list[int] = []

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if not isinstance(target, ast.Subscript):
                continue

            try:
                target_text = ast.unparse(target)
            except Exception:
                continue

            if target_text == "result['confluence_v2']":
                lines.append(node.lineno)

    return sorted(lines)


def _confluence_approved_read_lines() -> list[int]:
    lines: list[int] = []

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue

        if not isinstance(node.func, ast.Attribute):
            continue

        if node.func.attr != "get":
            continue

        try:
            owner = ast.unparse(node.func.value)
        except Exception:
            continue

        if owner != "result['confluence_v2']":
            continue

        if not node.args:
            continue

        try:
            key = ast.literal_eval(node.args[0])
        except Exception:
            continue

        if key == "approved":
            lines.append(node.lineno)

    return sorted(lines)


def test_exactly_two_confluence_evaluations_exist():
    assert len(_confluence_calls()) == 2


def test_early_confluence_is_not_published_as_final_authority():
    calls = _confluence_calls()

    early_line = calls[0].lineno
    late_line = calls[1].lineno

    premature_publications = [
        line
        for line in _result_assignment_lines()
        if early_line < line < late_line
    ]

    assert premature_publications == []


def test_early_confluence_execution_reads_remain_membership_guarded():
    calls = _confluence_calls()

    early_line = calls[0].lineno
    late_line = calls[1].lineno

    approved_reads = [
        line
        for line in _confluence_approved_read_lines()
        if early_line < line < late_line
    ]

    assert len(approved_reads) == 2
    assert approved_reads == sorted(approved_reads)


def test_runtime_risk_authority_does_not_exist_before_early_confluence():
    early_line = _confluence_calls()[0].lineno

    assert not any(
        line < early_line
        for line in _authority_assignments(
            "account_risk_approved"
        )
    )


def test_runtime_sizing_authority_does_not_exist_before_early_confluence():
    early_line = _confluence_calls()[0].lineno

    assert not any(
        line < early_line
        for line in _authority_assignments(
            "position_sizing_approved"
        )
    )


def test_early_confluence_currently_uses_static_allow_placeholders():
    early = _confluence_calls()[0]

    assert _keyword_value(
        early,
        "risk_approved",
    ) == "True"

    assert _keyword_value(
        early,
        "sizing_approved",
    ) == "True"


def test_final_confluence_occurs_after_runtime_authorities_exist():
    late_line = _confluence_calls()[1].lineno

    assert any(
        line < late_line
        for line in _authority_assignments(
            "account_risk_approved"
        )
    )

    assert any(
        line < late_line
        for line in _authority_assignments(
            "position_sizing_approved"
        )
    )


def test_final_confluence_uses_runtime_authority_sources():
    late = _confluence_calls()[1]

    risk_source = (
        _keyword_value(
            late,
            "risk_approved",
        )
        or ""
    )

    sizing_source = (
        _keyword_value(
            late,
            "sizing_approved",
        )
        or ""
    )

    assert "account_risk_approved" in risk_source
    assert "position_sizing_approved" in sizing_source
