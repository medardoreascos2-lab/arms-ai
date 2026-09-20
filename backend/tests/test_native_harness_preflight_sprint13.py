"""Synthetic CLI orchestration only; never open NinjaTrader or certify a feed."""
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

@pytest.fixture
def api_settings(monkeypatch):
    profile = json.loads(Path("backend/tests/paper_rc_certification_sprint08.json").read_text())["test_environment"]
    for key, value in profile.items():
        monkeypatch.setenv(key, str(value))


def prepare(tmp_path, monkeypatch, at="2026-09-21T00:00:00+00:00"):
    from backend.market_data import native_certification_v1 as cli
    from backend.market_data import native_calendar_review_v1 as review
    spec = json.loads(Path("backend/tests/native_capture_spec_sprint13.json").read_text())
    template = tmp_path / "synthetic.xml"
    template.write_text("SYNTHETIC TEST ONLY")
    spec["calendar_evidence_file"] = str(template)
    spec.pop("loaded_calendar_evidence_file")
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    monkeypatch.setattr(review, "validate_native_spec", lambda *a, **kw: {"loaded_native_calendar": "PASS"})
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(at)
    monkeypatch.setattr(cli, "datetime", Clock)
    directory = tmp_path / "evidence"
    directory.mkdir()
    old = directory / "old.jsonl"
    old.write_text("PRESERVE OLD SYNTHETIC EVIDENCE")
    monkeypatch.setattr("sys.argv", ["capture", "--spec", str(path), "--directory", str(directory),
        "--state", str(tmp_path / "state.sqlite"), "--output", str(tmp_path / "report.json"),
        "--purpose", "market_open", "--seconds", "7500"])
    return cli, directory, old


def test_real_reader_accepts_cli_provider_mapping_without_account_initialization(api_settings, tmp_path, monkeypatch):
    cli, directory, old = prepare(tmp_path, monkeypatch)
    selected = []
    # Trigger exactly one new synthetic filename after the existing-file snapshot.
    monkeypatch.setattr(cli.time, "sleep", lambda _: (directory / "fresh.jsonl").write_text("SYNTHETIC"))
    class Capture:
        def __init__(self, reader, **kwargs):
            selected.append(reader)
            self.fault = None
            self.frame_times = {}
        def poll(self):
            raise ValueError("INTENTIONAL_SYNTHETIC_STOP_BEFORE_INGESTION")
        def report(self):
            return {"status": "FAIL_CLOSED", "observed_market_milestones_complete": False}
        def close(self):
            selected[0].close()
    monkeypatch.setattr(cli, "NativeCertificationCaptureV1", Capture)
    cli.main()
    reader = selected[0]
    assert reader.provider == "Provider31"
    assert reader.service.gate.contract.provider == "NINJATRADER:Provider31"
    assert reader.path.name == "fresh.jsonl"
    assert reader.service._runtime is None
    assert not (tmp_path / "state.sqlite").exists()
    assert old.read_text() == "PRESERVE OLD SYNTHETIC EVIDENCE"
    assert json.loads((tmp_path / "report.json").read_text())["status"] == "FAIL_CLOSED"


@pytest.mark.parametrize("at", ["2026-09-20T23:59:59+00:00", "2026-09-28T00:00:00+00:00",
    "2026-09-27T23:00:00+00:00", "2026-09-21T20:00:00+00:00", "2026-09-21T21:30:00+00:00",
    "2026-09-26T12:00:00+00:00"])
def test_no_watch_outside_complete_open_capture_window(api_settings, tmp_path, monkeypatch, at):
    cli, _, _ = prepare(tmp_path, monkeypatch, at)
    monkeypatch.setattr(cli.time, "sleep", lambda _: pytest.fail("must not watch"))
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert not (tmp_path / "state.sqlite").exists()
    assert not (tmp_path / "report.json").exists()


def test_missing_risk_settings_blocks_before_native_activation(api_settings, tmp_path, monkeypatch):
    cli, _, _ = prepare(tmp_path, monkeypatch)
    monkeypatch.delenv("ARMS_MAXIMUM_QUOTE_AGE_SECONDS")
    monkeypatch.setattr(cli.time, "sleep", lambda _: pytest.fail("must not watch"))
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert not (tmp_path / "state.sqlite").exists()
    assert not (tmp_path / "report.json").exists()
