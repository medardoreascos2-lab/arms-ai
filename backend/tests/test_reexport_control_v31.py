"""Reproducibility tests and explicit admission-blocker witnesses.

Execution witnesses use synthetic plans/spy lifecycle state, not fresh strategy
outcomes. No scores, production thresholds or source files are modified.
"""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from types import SimpleNamespace

import pytest

from backend.backtesting.backtest_execution_simulator_v2 import BacktestExecutionSimulatorV2
from backend.backtesting.backtest_session_v2 import BacktestSessionV2
from backend.models.candle import Candle
from backend.tests.research_reexport_control_v31 import annotate_exceptions, compare_control
from backend.tests.test_production_certified_outcome_v17 import api_settings


@pytest.mark.parametrize("suffix", [False, True])
def test_exact_control_identity_and_coverage_not_hash_equality(tmp_path, suffix):
    content = b"20250330 165800;100;100;100;100;1\n20250330 165900;101;101;101;101;2\n"
    source, control = tmp_path/"original.txt", tmp_path/"control.txt"
    source.write_bytes(content)
    control.write_bytes(content.splitlines(keepends=True)[-1] if suffix else content)
    before = source.read_bytes(), control.read_bytes()
    result = compare_control(source, control, sha256(content).hexdigest())
    assert result["shared_row_differences"] == 0
    assert result["suffix_start_1based"] == (2 if suffix else 1)
    assert result["byte_equal"] is (not suffix)
    assert (source.read_bytes(), control.read_bytes()) == before


def test_control_mismatch_cannot_be_certified(tmp_path):
    source, control = tmp_path/"original.txt", tmp_path/"control.txt"
    source.write_bytes(b"a\nb\n")
    control.write_bytes(b"a\nc\n")
    with pytest.raises(ValueError, match="differs"):
        compare_control(source, control, sha256(source.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="hash"):
        compare_control(source, control, "0"*64)


def test_control_coverage_does_not_spread_to_other_rows_or_contracts():
    rows = [{"line": i, "source_row": f"unchanged-{i}", "admitted": False} for i in (1, 2)]
    records = [{"contract": c, "sha256": "a" * 64, "prior_exceptions": rows} for c in ("MAR25", "JUN25", "JUN22")]
    controls = {c: {"source_sha256": "a" * 64, "source_rows": 2,
                    "suffix_start_1based": start, "control_rows": 3-start,
                    "shared_rows_exact": 3-start, "shared_row_differences": 0}
                for c, start in (("MAR25", 1), ("JUN25", 2))}
    before = deepcopy((records, controls))
    result = annotate_exceptions(records, controls)
    assert len(result) == 6
    assert [r["directly_reproduced"] for r in result] == [True, True, False, True, False, False]
    assert all(r["observation_disposition"] == "PRESERVE_AND_FLAG" for r in result)
    assert all(r["execution_admissibility"] == "UNRESOLVED" for r in result)
    assert rows == [{"line": i, "source_row": f"unchanged-{i}", "admitted": False} for i in (1, 2)]
    assert (records, controls) == before


@pytest.fixture
def control_evidence(tmp_path):
    source, control = tmp_path / "source.txt", tmp_path / "control.txt"
    lines = [f"20250330 170{i}00;100;100;100;100;{i}\n".encode() for i in range(5)]
    source.write_bytes(b"".join(lines))
    control.write_bytes(b"".join(lines[2:]))
    metadata = compare_control(source, control, sha256(source.read_bytes()).hexdigest())
    record = {"contract": "MAR25", "sha256": metadata["source_sha256"], "rows": 5,
              "prior_exceptions": [{"line": 3, "source_row": lines[2].decode().rstrip(), "admitted": False}]}
    return record, {"MAR25": metadata}, source, control


def check_annotation_unchanged(record, controls, source, control, expected):
    before = deepcopy((record, controls))
    files_before = source.read_bytes(), control.read_bytes()
    result = annotate_exceptions([record], controls)[0]
    assert result["directly_reproduced"] is expected
    assert result["reproduction_basis"] == ("EXACT_CONTROL_ROW" if expected else "COHORT_INFERENCE_ONLY")
    assert result["execution_admissibility"] == "UNRESOLVED"
    assert result["observation_disposition"] == "PRESERVE_AND_FLAG"
    assert result["admitted"] is False
    assert result["not_a_normal_session_assertion"] is True
    assert (record, controls) == before
    assert (source.read_bytes(), control.read_bytes()) == files_before


@pytest.mark.parametrize("line,expected", [(2, False), (3, True), (4, True), (5, True), (6, False),
                                         (0, False), (-1, False), (True, False), (3.0, False), ("3", False)])
def test_direct_reproduction_requires_exact_closed_coverage(control_evidence, line, expected):
    record, controls, source, control = control_evidence
    record["prior_exceptions"][0]["line"] = line
    check_annotation_unchanged(record, controls, source, control, expected)


@pytest.mark.parametrize("fault", ["wrong_hash", "missing_hash", "malformed_hash", "unrelated_contract",
                                  "contradictory_contract", "record_count"])
def test_direct_reproduction_requires_source_identity(control_evidence, fault):
    record, controls, source, control = control_evidence
    metadata = controls["MAR25"]
    if fault == "wrong_hash": metadata["source_sha256"] = "b" * 64
    elif fault == "missing_hash": del metadata["source_sha256"]
    elif fault == "malformed_hash": record["sha256"] = metadata["source_sha256"] = "not-a-digest"
    elif fault == "unrelated_contract": controls["JUN25"] = controls.pop("MAR25")
    elif fault == "contradictory_contract": metadata["contract"] = "JUN25"
    elif fault == "record_count": record["rows"] = 6
    check_annotation_unchanged(record, controls, source, control, False)


@pytest.mark.parametrize("field", ["source_rows", "control_rows", "suffix_start_1based", "shared_rows_exact", "shared_row_differences"])
@pytest.mark.parametrize("fault", ["missing", "bool", "inconsistent"])
def test_unproven_control_coverage_fails_closed(control_evidence, field, fault):
    record, controls, source, control = control_evidence
    metadata = controls["MAR25"]
    if fault == "missing": del metadata[field]
    elif fault == "bool": metadata[field] = True
    else: metadata[field] += 1
    check_annotation_unchanged(record, controls, source, control, False)


def flagged_candle():
    # Values from the independently reproduced final JUN25 row. This is a test
    # fixture, not a claim that any strategy opened the hypothetical trade below.
    c = Candle("NQ", "1m", 21865.25, 21865.25, 21865.25, 21865.25, 5,
               datetime.fromisoformat("2025-06-22T10:51:00-05:00"))
    c.session_anomaly = True
    return c


def test_witness_current_candle_normalization_drops_advisory_flags():
    normalized = BacktestSessionV2._normalize_candle(flagged_candle())
    assert "session_anomaly" not in normalized
    assert normalized["close"] == 21865.25


def test_witness_production_composition_supplies_constant_market_open(api_settings):
    from backend.backtesting.parameter_backtest_engine_factory_v2 import ParameterBacktestEngineFactoryV2
    engine = ParameterBacktestEngineFactoryV2(csv_path=None, settings=api_settings)(
        {"ema": 10, "stop_loss": 30, "take_profit": 60})
    session = engine.pipeline.pipeline.backtest_session_v2
    assert session.signal_order_context == {"market_is_open": True}
    assert session.signal_submission_target_v2.execution_manager.execution_mode == "PAPER"
    assert session.backtest_runner_v2.replay_market_data_bridge_v2.market_data_hub_v2 is None


def test_witness_existing_simulator_uses_flagged_sunday_price_for_take_profit():
    trade = BacktestExecutionSimulatorV2().simulate(
        symbol="NQ", direction="BUY", entry=21805.25,
        stop_loss=21775.25, take_profit=21865.25, contracts=1,
        risk_amount=600, candles=[flagged_candle()],
    )
    assert trade.status == "WIN"
    assert trade.pnl == 1200
    assert trade.reasoning[0] == "TAKE_PROFIT"


def test_witness_existing_position_update_consumes_flagged_price_before_strategy():
    calls = []
    def update(**kwargs):
        calls.append(kwargs)
        return {"updated": True, "position": {"status": "OPEN"}}
    session = SimpleNamespace(active_position_id="TEST-POSITION",
                              signal_submission_target_v2=SimpleNamespace(update_position=update),
                              position_update_results=[])
    row = {**vars(flagged_candle())}
    BacktestSessionV2._update_active_position_if_configured(session, candle=row)
    assert calls == [{"position_id": "TEST-POSITION", "current_price": 21865.25}]
    assert len(session.position_update_results) == 1
