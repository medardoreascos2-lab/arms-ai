from pathlib import Path
import ast


APP_FILE = Path("backend/api/app.py")


def _tree() -> ast.Module:
    return ast.parse(
        APP_FILE.read_text(
            encoding="utf-8",
            errors="strict",
        ),
        filename=str(APP_FILE),
    )


def _position_sizing_constructor() -> ast.Call:
    matches = []

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue

        name = None

        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr

        if name == "PositionSizingEngine":
            matches.append(node)

    assert len(matches) == 1

    return matches[0]


def _runtime_limit_assignment() -> ast.Assign:
    matches = []

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if (
                isinstance(target, ast.Name)
                and target.id
                == "active_runtime_contract_limit"
            ):
                matches.append(node)

    assert len(matches) == 1

    return matches[0]


def _position_sizing_runtime_assignment() -> ast.Assign:
    matches = []

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id
                == "position_sizing_engine"
                and target.attr
                == "maximum_contracts"
                and isinstance(node.value, ast.Name)
                and node.value.id
                == "active_runtime_contract_limit"
            ):
                matches.append(node)

    assert len(matches) == 1

    return matches[0]


def _position_sizing_resolver_assignment() -> ast.Assign:
    matches = []

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id
                == "position_sizing_engine"
                and target.attr
                == "contract_limit_resolver"
            ):
                matches.append(node)

    assert len(matches) == 1

    return matches[0]


def test_position_sizing_runtime_authority_overrides_bootstrap_limit():
    constructor = _position_sizing_constructor()
    authority = _position_sizing_runtime_assignment()

    maximum_contracts = [
        kw.value
        for kw in constructor.keywords
        if kw.arg == "maximum_contracts"
    ]

    assert len(maximum_contracts) == 1

    value = maximum_contracts[0]

    assert isinstance(value, ast.Constant)
    assert value.value == 20

    assert authority.lineno > constructor.lineno


def test_runtime_limit_exists_before_position_sizing_authority_assignment():
    runtime_limit = _runtime_limit_assignment()
    authority = _position_sizing_runtime_assignment()

    assert runtime_limit.lineno < authority.lineno


def test_position_sizing_authority_is_set_before_dynamic_resolver():
    authority = _position_sizing_runtime_assignment()
    resolver = _position_sizing_resolver_assignment()

    assert authority.lineno < resolver.lineno


def test_runtime_consumers_share_active_contract_limit_authority():
    expected = {
        "RiskManagerV2",
        "ExecutionManagerV2",
    }

    found = set()

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue

        name = None

        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr

        if name not in expected:
            continue

        maximum_contracts = [
            kw.value
            for kw in node.keywords
            if kw.arg == "maximum_contracts"
        ]

        assert len(maximum_contracts) == 1

        value = maximum_contracts[0]

        assert isinstance(value, ast.Name)

        assert (
            value.id
            == "active_runtime_contract_limit"
        )

        found.add(name)

    assert found == expected
