from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.instruments.instrument_profile_engine import (
    InstrumentProfileEngine,
)


ROOT = Path(__file__).resolve().parents[2]

APP_PATH = ROOT / "backend" / "api" / "app.py"
API_SETTINGS_PATH = (
    ROOT / "backend" / "config" / "api_settings.py"
)
RUNTIME_CONTEXT_PATH = (
    ROOT / "backend" / "services" / "runtime_context_v2.py"
)
BACKTEST_FACTORY_PATH = (
    ROOT
    / "backend"
    / "backtesting"
    / "strategy_backtest_factory_v2.py"
)


def _source(path: Path) -> str:
    return path.read_text(
        encoding="utf-8",
        errors="strict",
    )


def _point_value_calls(path: Path):
    tree = ast.parse(
        _source(path),
        filename=str(path),
    )

    records = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            call_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
        else:
            continue

        for keyword in node.keywords:
            if keyword.arg != "point_value":
                continue

            records.append(
                (
                    node.lineno,
                    call_name,
                    keyword.value,
                )
            )

    return records


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("MNQ", 2.0),
        ("NQ", 20.0),
        ("MES", 5.0),
        ("ES", 50.0),
    ],
)
def test_instrument_profile_is_canonical_point_value_authority(
    symbol: str,
    expected: float,
) -> None:
    profile = InstrumentProfileEngine().get_profile(
        symbol=symbol
    )

    assert float(profile["point_value"]) == expected


def test_api_settings_does_not_define_global_point_value_authority() -> None:
    tree = ast.parse(
        _source(API_SETTINGS_PATH),
        filename=str(API_SETTINGS_PATH),
    )

    names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)

        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)

    assert "point_value" not in names
    assert (
        "ARMS_POINT_VALUE"
        not in _source(API_SETTINGS_PATH)
    )


def test_runtime_context_uses_dynamic_point_value_authority() -> None:
    records = _point_value_calls(
        RUNTIME_CONTEXT_PATH
    )

    position_manager_records = [
        value
        for _, call_name, value in records
        if call_name == "PositionManagerV2"
    ]

    assert position_manager_records

    rendered = {
        ast.unparse(value)
        for value in position_manager_records
    }

    assert "resolved_settings.point_value" in rendered


def test_backtest_uses_dynamic_point_value_authority() -> None:
    records = _point_value_calls(
        BACKTEST_FACTORY_PATH
    )

    position_manager_records = [
        value
        for _, call_name, value in records
        if call_name == "PositionManagerV2"
    ]

    assert position_manager_records

    assert all(
        not isinstance(value, ast.Constant)
        for value in position_manager_records
    )


@pytest.mark.parametrize(
    "target_call",
    [
        "PositionManagerV2",
        "RealizedPnLEngineV2",
    ],
)
def test_api_app_does_not_hardcode_point_value(
    target_call: str,
) -> None:
    records = _point_value_calls(APP_PATH)

    target_records = [
        (line, value)
        for line, call_name, value in records
        if call_name == target_call
    ]

    assert target_records, (
        f"{target_call} debe existir en app.py"
    )

    literal_records = [
        (line, ast.unparse(value))
        for line, value in target_records
        if isinstance(value, ast.Constant)
        and isinstance(
            value.value,
            (int, float),
        )
    ]

    assert not literal_records, (
        f"{target_call} no debe recibir un "
        "point_value numérico global hardcoded; "
        "la autoridad es específica por instrumento. "
        f"Encontrado: {literal_records}"
    )


def test_api_app_has_no_global_two_point_value_authority() -> None:
    records = _point_value_calls(APP_PATH)

    offending = []

    for line, call_name, value in records:
        if not isinstance(value, ast.Constant):
            continue

        if not isinstance(
            value.value,
            (int, float),
        ):
            continue

        if float(value.value) == 2.0:
            offending.append(
                (
                    line,
                    call_name,
                    float(value.value),
                )
            )

    assert not offending, (
        "app.py no puede asumir globalmente "
        "MNQ=$2/point para motores operacionales "
        f"multiinstrumento: {offending}"
    )
