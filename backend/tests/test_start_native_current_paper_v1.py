"""Offline ownership tests; no actual launcher, listener, or native process."""

from pathlib import Path
from threading import Event
from types import SimpleNamespace
import json
import time
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

import tools.start_native_current_paper_v1 as launcher
from backend.api.current_paper_app_v1 import create_current_paper_app_v1
from backend.tests.test_analysis_native_lifecycle_hook_v1 import ready_runtime
from backend.tests.test_certified_native_paper_bridge_v1 import _paper
from backend.tests.test_production_certified_outcome_v17 import api_settings
from tools.analysis_native_startup_v1 import _build_optional_lifecycle


def _args(tmp_path):
    spec = {
        "calendar_evidence_file": str(tmp_path / "template.xml"),
        "loaded_calendar_evidence_file": str(tmp_path / "loaded.jsonl"),
    }
    (tmp_path / "template.xml").write_bytes(b"template")
    (tmp_path / "loaded.jsonl").write_bytes(b"loaded")
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    from hashlib import sha256
    return SimpleNamespace(
        start_current_paper=True,
        port=18001, frontend_port=13001, paper_port=18002,
        startup_chart_catchup_timeout=300.0,
        paper_run_namespace=tmp_path / "paper-run",
        native_spec=spec_path,
        native_spec_sha256=sha256(spec_path.read_bytes()).hexdigest(),
        paper_config=tmp_path / "paper-config.json",
        admin_token_env="ARMS_TEST_PAPER_ADMIN_TOKEN",
    )


class _Socket:
    def __init__(self, events):
        self.events = events
        self.closed = False

    def close(self):
        self.closed = True
        self.events.append("socket_close")


class _Server:
    def __init__(self, config, events):
        self.config = config
        self.events = events
        self.started = False
        self.should_exit = False

    def run(self, *, sockets):
        assert len(sockets) == 1
        self.events.append("api_start")
        self.started = True
        while not self.should_exit:
            time.sleep(0.001)
        self.events.append("api_stop")


def _offline_wiring(
    tmp_path, monkeypatch, *, fail_before_hook=False, fail_after_hook=False,
):
    args = _args(tmp_path)
    events = []
    service = SimpleNamespace(shutdown=lambda: events.append("service_shutdown"))
    shared = []
    bound = _Socket(events)
    monkeypatch.setenv(args.admin_token_env, "test-only-secret")
    monkeypatch.setattr(launcher, "_reserve_paper_port", lambda port: bound)

    import backend.backtesting.paper_research_v1 as paper_config
    import backend.config.api_settings as settings_module
    import backend.api.current_paper_app_v1 as paper_api
    import tools.analysis_native_startup_v1 as analysis
    import uvicorn

    monkeypatch.setattr(settings_module, "APISettings", lambda: object())
    monkeypatch.setattr(paper_config.PaperResearchConfigV1, "load", lambda path: object())

    def make_service(**kwargs):
        shared.append(("factory", kwargs))
        return service

    def make_app(**kwargs):
        shared.append(("api", kwargs))
        return object()

    class FakeNativeLifecycle:
        def __init__(self, *, analysis_runtime, service, wall_clock):
            shared.append(("lifecycle", service))
            events.append("attach_at_seam")

        def start(self):
            events.append("worker_start")

        def check(self):
            events.append("worker_check")

        def close(self):
            events.extend(("worker_stop", "coordinator_close"))

    class FakeServer(_Server):
        def __init__(self, config):
            super().__init__(config, events)

    monkeypatch.setattr(launcher, "create_certified_current_paper_service_v1", make_service)
    monkeypatch.setattr(paper_api, "create_current_paper_app_v1", make_app)
    monkeypatch.setattr(launcher, "NativeCurrentPaperLifecycleV1", FakeNativeLifecycle)
    def fake_config(app, **kwargs):
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == args.paper_port
        return (app, kwargs)

    monkeypatch.setattr(uvicorn, "Config", fake_config)
    monkeypatch.setattr(uvicorn, "Server", FakeServer)

    def fake_run(analysis_args, lifecycle_factory):
        assert analysis_args is args
        assert events == []
        if fail_before_hook:
            raise RuntimeError("ANALYSIS_START_FAILED")
        runtime = ready_runtime()
        owner = _build_optional_lifecycle(
            lifecycle_factory,
            runtime=runtime,
            run_directory=tmp_path / "analysis-run",
            catchup_source=tmp_path / "catchup.cs",
            validate_offline=False,
        )
        try:
            owner.start()
            owner.check()
            if fail_after_hook:
                raise RuntimeError("HEALTH_AFTER_ATTACH_FAILED")
        finally:
            owner.close()
            events.append("analysis_runtime_close")
        return "analysis_done"

    monkeypatch.setattr(analysis, "run", fake_run)
    return args, events, shared, bound, service


def test_separate_cli_single_service_seam_loopback_and_shutdown_order(
    tmp_path, monkeypatch,
):
    args, events, shared, bound, service = _offline_wiring(tmp_path, monkeypatch)
    assert launcher.run_current_paper(args) == "analysis_done"
    assert [kind for kind, _ in shared] == ["factory", "api", "lifecycle"]
    assert shared[1][1]["service"] is service
    assert shared[2][1] is service
    assert shared[0][1]["state_path"] == args.paper_run_namespace / "paper.sqlite"
    assert shared[1][1]["admin_token"] == "test-only-secret"
    assert events.index("attach_at_seam") < events.index("worker_start")
    assert events.index("worker_start") < events.index("api_start")
    assert events.index("worker_stop") < events.index("coordinator_close")
    assert events.index("coordinator_close") < events.index("api_stop")
    assert events.index("api_stop") < events.index("analysis_runtime_close")
    assert bound.closed


def test_startup_failure_before_seam_closes_owned_paper_resources(
    tmp_path, monkeypatch,
):
    args, events, shared, bound, _ = _offline_wiring(
        tmp_path, monkeypatch, fail_before_hook=True,
    )
    with pytest.raises(RuntimeError, match="ANALYSIS_START_FAILED"):
        launcher.run_current_paper(args)
    assert [kind for kind, _ in shared] == ["factory", "api"]
    assert bound.closed
    assert "service_shutdown" in events
    assert "api_start" not in events


def test_failure_after_seam_closes_worker_then_api_before_analysis(
    tmp_path, monkeypatch,
):
    args, events, _, bound, _ = _offline_wiring(
        tmp_path, monkeypatch, fail_after_hook=True,
    )
    with pytest.raises(RuntimeError, match="HEALTH_AFTER_ATTACH_FAILED"):
        launcher.run_current_paper(args)
    assert events.index("coordinator_close") < events.index("api_stop")
    assert events.index("api_stop") < events.index("analysis_runtime_close")
    assert bound.closed


@pytest.mark.parametrize("ports", (
    (18001, 18001, 18002), (18001, 13001, 13001), (0, 13001, 18002),
))
def test_three_ports_are_required_distinct_and_bounded(tmp_path, ports):
    args = _args(tmp_path)
    args.port, args.frontend_port, args.paper_port = ports
    with pytest.raises(ValueError, match="DISTINCT_PORTS_REQUIRED"):
        launcher.run_current_paper(args)
    assert not args.paper_run_namespace.exists()


def test_missing_admin_token_fails_before_authority_construction(tmp_path, monkeypatch):
    args = _args(tmp_path)
    monkeypatch.delenv(args.admin_token_env, raising=False)
    with pytest.raises(ValueError, match="EXPLICIT_ADMIN_TOKEN_REQUIRED"):
        launcher.run_current_paper(args)
    assert not args.paper_run_namespace.exists()


def test_unreviewed_spec_cannot_open_its_evidence_paths(tmp_path, monkeypatch):
    args = _args(tmp_path)
    args.native_spec_sha256 = "0" * 64
    monkeypatch.setenv(args.admin_token_env, "test-only-secret")
    with pytest.raises(ValueError, match="REVIEWED_NATIVE_SPEC_SHA256_REQUIRED"):
        launcher.run_current_paper(args)


def test_read_routes_cannot_enable_paper_and_post_requires_admin(
    tmp_path, api_settings, monkeypatch,
):
    service, _ = _paper(tmp_path, api_settings)
    control = Mock(side_effect=RuntimeError("AWAITING_MARKET_DATA"))
    monkeypatch.setattr(service, "control", control)
    app = create_current_paper_app_v1(service=service, admin_token="test-admin")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/v2/paper/readiness").status_code == 200
        assert control.call_count == 0
        assert client.post("/api/v2/paper/enable").status_code == 401
        assert control.call_count == 0
        assert client.post(
            "/api/v2/paper/enable", headers={"X-ARMS-ADMIN-TOKEN": "test-admin"},
        ).status_code == 409
    assert control.call_count == 1


def test_public_analysis_cli_and_old_operational_owner_are_not_imported():
    source = Path(launcher.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "start_analysis_native_v1", "operational_paper_soak_v1",
        "operational_paper_v1", "ninjatrader_market_reader_v1",
        'service.control("enable")', "SubmitOrder", "CreateOrder(",
    ):
        assert forbidden not in source
    assert 'bound.bind(("127.0.0.1", port))' in source
