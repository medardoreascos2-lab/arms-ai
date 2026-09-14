from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from backend.execution.execution_risk_gate_v1 import (
    ExecutionRiskGateV1,
)
from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)
from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
)


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


def test_risk_authority_components_are_present() -> None:
    expected_files = (
        "account/account_state_manager_v2.py",
        "accounts/account_config_manager_v2.py",
        "execution/risk_manager_v2.py",
        "execution/execution_risk_gate_v1.py",
        "execution/trade_validator_v2.py",
        "execution/position_sizing_engine_v2.py",
        "execution/exposure_manager_v2.py",
        "execution/portfolio_risk_engine_v2.py",
        "risk/trade_risk_validator_v2.py",
        "services/economic_news_authority_v2.py",
        "services/price_feed_service_v2.py",
    )

    for relative_path in expected_files:
        source = _source(relative_path)
        assert source.strip()
        assert _defined_names(source), relative_path


def test_risk_components_expose_fail_closed_vocabulary() -> None:
    risk_files = (
        "execution/risk_manager_v2.py",
        "execution/execution_risk_gate_v1.py",
        "execution/trade_validator_v2.py",
        "risk/trade_risk_validator_v2.py",
        "services/economic_news_authority_v2.py",
        "services/price_feed_service_v2.py",
    )
    combined = "\n".join(_source(path) for path in risk_files).lower()

    assert "reject" in combined or "block" in combined
    assert "invalid" in combined or "missing" in combined
    assert "risk" in combined
    assert "fail" in combined or "closed" in combined


def test_risk_authority_sources_include_required_control_domains() -> None:
    sources = {
        "account": _source("account/account_state_manager_v2.py").lower(),
        "configuration": _source(
            "accounts/account_config_manager_v2.py"
        ).lower(),
        "execution_risk": _source("execution/risk_manager_v2.py").lower(),
        "gate": _source("execution/execution_risk_gate_v1.py").lower(),
        "validator": _source("execution/trade_validator_v2.py").lower(),
        "sizing": _source(
            "execution/position_sizing_engine_v2.py"
        ).lower(),
        "exposure": _source("execution/exposure_manager_v2.py").lower(),
        "portfolio_risk": _source(
            "execution/portfolio_risk_engine_v2.py"
        ).lower(),
    }

    assert "daily" in sources["account"]
    assert "account" in sources["configuration"]
    assert "drawdown" in sources["execution_risk"]
    assert "stop" in sources["validator"]
    assert "size" in sources["sizing"] or "contract" in sources["sizing"]
    assert "exposure" in sources["exposure"]
    assert "portfolio" in sources["portfolio_risk"]
    assert "approve" in sources["gate"] or "block" in sources["gate"]


def test_execution_gate_rejects_non_finite_risk_before_validator_side_effects() -> None:
    class ValidatorProbe:
        def __init__(self) -> None:
            self.calls = 0

        def validate_trade(
            self,
            contracts: int,
            risk_amount: float,
            symbol: str | None = None,
        ) -> dict[str, object]:
            self.calls += 1
            return {
                "status": "APPROVED",
                "account": "UNEXPECTED",
            }

    validator = ValidatorProbe()
    gate = ExecutionRiskGateV1(
        validator=validator,
    )

    with pytest.raises(ValueError):
        gate.evaluate_trade(
            symbol="MNQ",
            side="BUY",
            contracts=1,
            risk_amount=math.nan,
        )

    assert validator.calls == 0
    assert gate.get_risk_events() == []


def test_risk_manager_rejects_non_finite_context_before_sizing() -> None:
    class SizingProbe:
        def calculate(self, **kwargs: object) -> dict[str, object]:
            raise AssertionError(
                "Position sizing must not run for invalid risk context."
            )

    risk_manager = object.__new__(RiskManagerV2)
    risk_manager.position_sizing_engine = SizingProbe()
    risk_manager.maximum_daily_loss = 1_000.0
    risk_manager.maximum_total_drawdown = 2_000.0
    risk_manager.maximum_contracts = 10
    risk_manager.maximum_open_positions = 1
    risk_manager.contract_limit_resolver = None

    with pytest.raises(ValueError):
        risk_manager.evaluate(
            account_balance=50_000.0,
            risk_percent=math.nan,
            stop_points=10.0,
            point_value=20.0,
            daily_pnl=0.0,
            total_drawdown=0.0,
            open_positions=0,
        )
