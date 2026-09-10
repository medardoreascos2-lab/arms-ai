from __future__ import annotations

import ast
from pathlib import Path

from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)
from backend.risk.multi_account_risk_engine_v2 import (
    MultiAccountRiskEngineV2,
)


INTELLIGENCE_PATH = Path(
    "backend/api/routers/intelligence_decision_api_v3.py"
)

MARKET_PATH = Path(
    "backend/api/routers/market.py"
)


def _risk_percent_literal_keywords(
    path: Path,
) -> list[ast.keyword]:
    tree = ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
    )

    return [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.keyword)
            and node.arg == "risk_percent"
            and isinstance(
                node.value,
                (
                    ast.Constant,
                    ast.UnaryOp,
                ),
            )
        )
    ]


def test_active_account_profile_is_risk_percent_authority():
    manager = AccountConfigManagerV2()

    engine = MultiAccountRiskEngineV2(
        account_manager=manager,
    )

    active_profile = engine.get_active_risk_profile()

    assert "risk_percent" in active_profile

    assert active_profile["risk_percent"] == (
        manager.get_active_account().risk_percent
    )


def test_intelligence_router_has_no_literal_risk_percent():
    literals = _risk_percent_literal_keywords(
        INTELLIGENCE_PATH
    )

    assert literals == []


def test_market_router_has_no_literal_risk_percent():
    literals = _risk_percent_literal_keywords(
        MARKET_PATH
    )

    assert literals == []


def _risk_percent_literal_dict_values(
    path: Path,
) -> list[tuple[int, ast.expr]]:
    tree = ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
    )

    literals: list[tuple[int, ast.expr]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue

        for key, value in zip(
            node.keys,
            node.values,
        ):
            if not (
                isinstance(key, ast.Constant)
                and key.value == "risk_percent"
            ):
                continue

            if isinstance(
                value,
                (
                    ast.Constant,
                    ast.UnaryOp,
                ),
            ):
                literals.append(
                    (
                        key.lineno,
                        value,
                    )
                )

    return literals


def test_intelligence_router_has_no_literal_risk_percent_dict_values():
    literals = _risk_percent_literal_dict_values(
        INTELLIGENCE_PATH
    )

    assert literals == []


def test_intelligence_router_references_runtime_risk_authority():
    source = INTELLIGENCE_PATH.read_text(
        encoding="utf-8"
    )

    assert (
        "active_risk_profile" in source
        or "risk_percent" in source
    )

    assert (
        "AccountConfigManagerV2" in source
        or "MultiAccountRiskEngineV2" in source
        or "request.app.state" in source
    )


def test_market_router_references_runtime_risk_authority():
    source = MARKET_PATH.read_text(
        encoding="utf-8"
    )

    assert (
        "active_risk_profile" in source
        or "risk_percent" in source
    )

    assert (
        "AccountConfigManagerV2" in source
        or "MultiAccountRiskEngineV2" in source
        or "request.app.state" in source
    )
