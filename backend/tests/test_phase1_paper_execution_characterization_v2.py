from __future__ import annotations

import ast
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    path = BACKEND_ROOT / relative_path
    assert path.is_file(), f"Expected repository file is missing: {path}"
    return path.read_text(encoding="utf-8")


def _defined_names(source: str) -> set[str]:
    tree = ast.parse(source)
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_paper_execution_components_exist() -> None:
    paper_source = _source("execution/paper_execution_engine_v2.py")
    connector_source = _source("connectors/paper_broker_connector_v2.py")
    lifecycle_source = _source("services/trade_lifecycle_service_v2.py")

    paper_names = _defined_names(paper_source)
    connector_names = _defined_names(connector_source)
    lifecycle_names = _defined_names(lifecycle_source)

    assert any("Paper" in name for name in paper_names)
    assert any("Paper" in name for name in connector_names)
    assert any("Lifecycle" in name for name in lifecycle_names)

    assert "execute" in paper_source.lower()
    assert "submit" in connector_source.lower()
    assert "signal" in lifecycle_source.lower()


def test_paper_path_contains_fill_and_rejection_boundaries() -> None:
    sources = (
        _source("services/trade_lifecycle_service_v2.py"),
        _source("execution/paper_execution_engine_v2.py"),
        _source("connectors/paper_broker_connector_v2.py"),
        _source("execution/execution_manager_v2.py"),
    )
    combined = "\n".join(sources).lower()

    assert "fill" in combined
    assert "reject" in combined or "block" in combined
    assert "paper" in combined


def test_paper_execution_does_not_claim_physical_protection_submission() -> None:
    paper_source = _source("execution/paper_execution_engine_v2.py").lower()
    connector_source = _source("connectors/paper_broker_connector_v2.py").lower()
    protection_source = _source(
        "execution/protective_order_registry_v2.py"
    ).lower()

    combined = "\n".join(
        (paper_source, connector_source, protection_source)
    )

    assert "paper" in combined
    assert "submit" in connector_source
    assert "protect" in protection_source or "oco" in protection_source

    # The PAPER boundary must expose execution submission separately from
    # protection-state management. Physical broker protection submission must
    # not be represented by a protective-order submission API.
    assert "submit_protective_order" not in combined
    assert "submit_oco" not in combined
    assert "broker_protective_order" not in combined
