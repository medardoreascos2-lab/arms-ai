"""0.11A inventory: A-T, identity ambiguity and zero operational side effects."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from backend.services.legacy_state_inventory_v2 import LegacyStateInventoryV2
from backend.services.durable_execution_state_v2 import seal
from backend.tests.test_durable_crash_recovery_v2 import build_runtime, open_position

ASGI = "data/runtime/runtime-state-v2.json"
CLI = "data/runtime_state_v2.json"


@pytest.fixture
def states():
    lifecycle, account, store, _, _ = build_runtime()
    clean = store.capture_state()
    position = open_position(lifecycle)
    active = store.capture_state()
    lifecycle.update_position(position_id=position["position_id"], current_price=120.)
    closed = store.capture_state()
    return clean, active, closed


def write(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def audit(root, **kwargs):
    return LegacyStateInventoryV2(workspace_root=root, environment={}, **kwargs).dry_run()


def candidate(report, path):
    return next(row for row in report["candidates"] if row["normalized_path"] == str(path.resolve()))


def canonical(state, account_id="PAPER-A"):
    result = deepcopy(state)
    result["account_identity"] = {"account_id": account_id, "profile_name": "SAME", "runtime_generation": 1}
    result["execution_records"]["paper"]["account_id"] = account_id
    return result


@pytest.mark.parametrize("scenario", list("ABCDEFGHIJ"))
def test_a_to_j(tmp_path, states, scenario):
    clean, active, closed = states
    state = deepcopy(active if scenario in "HJ" else closed if scenario == "I" else clean)
    expected = "AMBIGUOUS"
    if scenario == "A":
        state = canonical(state)
    if scenario == "C":
        state["profile_name"] = "SAME"
    if scenario == "F":
        state["account_portfolio"]["account"]["state"]["daily_pnl"] = 123
        expected = "CORRUPT"
    if scenario == "G":
        state.pop("account_portfolio")
        expected = "INCOMPLETE"
    path = write(tmp_path, ASGI, seal(state, 1, "COMMITTED"))
    report = audit(tmp_path)
    row = candidate(report, path)
    assert row["classification"] == expected, row
    assert row["eligible"] is False and row["potential_destination"] is None
    assert row["identity_evidence"]["proven"] is False
    assert row["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    if scenario not in "FG":
        assert row["validation_results"] == {"structural": "PASS", "semantic": "PASS", "economic": "PASS"}
    if scenario in "HJ":
        assert row["open_activity"]["present"]
        assert "open_or_pending_activity_not_eligible" in row["rejection_reasons"]
    if scenario == "I":
        assert row["financial_summary"]["realized_pnl"] == 80
        assert row["participants"]["journal"]["count"] == 1
    if scenario == "A":
        assert row["identity_evidence"]["claimed"]["account_id"] == "PAPER-A"
    if scenario in "DE":
        other = write(tmp_path, CLI, seal(state, 1, "COMMITTED"))
        report = audit(tmp_path)
        assert candidate(report, other)["classification"] == "AMBIGUOUS"
        assert report["multiple_runtime_candidates"]
        assert report["selected_source"] is None


@pytest.mark.parametrize("selected", ["A", "B"])
def test_k_l_selector_never_identifies_global(tmp_path, states, selected):
    path = write(tmp_path, ASGI, seal(states[2], 1, "COMMITTED"))
    selector = write(tmp_path, "backend/config/accounts.json", {"active_account": selected})
    report = audit(tmp_path)
    assert candidate(report, path)["classification"] == "AMBIGUOUS"
    assert candidate(report, selector)["identity_evidence"]["profile_name"] == selected
    assert candidate(report, path)["potential_destination"] is None


def test_m_multiple_candidates_no_selection(tmp_path, states):
    paths = [write(tmp_path, name, seal(state, i+1, "COMMITTED"))
             for i, (name, state) in enumerate(zip((ASGI, CLI, "data/runtime/runtime-state-extra.json"), states))]
    report = audit(tmp_path)
    assert set(report["runtime_candidates"]) == {str(p.resolve()) for p in paths}
    assert report["multiple_runtime_candidates"] and report["selected_source"] is None


@pytest.mark.parametrize("relative", [ASGI, CLI])
def test_n_o_each_historical_path_discovered_independently(tmp_path, states, relative):
    path = write(tmp_path, relative, seal(states[0], 1, "COMMITTED"))
    report = audit(tmp_path)
    assert candidate(report, path)["exists"]
    other = tmp_path / (CLI if relative == ASGI else ASGI)
    assert candidate(report, other)["exists"] is False


def test_p_environment_and_explicit_paths_are_additional(tmp_path, states):
    paths = [write(tmp_path, p, seal(states[0], 1, "COMMITTED")) for p in (ASGI, CLI, "extra/env.json", "other/custom.json")]
    report = LegacyStateInventoryV2(workspace_root=tmp_path,
        environment={"ARMS_RUNTIME_STATE_PATH": "extra/env.json"}, state_paths=["other/custom.json"]).dry_run()
    assert set(report["runtime_candidates"]) == {str(p.resolve()) for p in paths}


def test_q_catalog_and_legacy_are_both_reported(tmp_path, states):
    global_path = write(tmp_path, CLI, seal(states[0], 1, "COMMITTED"))
    new_path = write(tmp_path, "accounts/PAPER-A/runtime-state.json", seal(canonical(states[0]), 2, "COMMITTED"))
    catalog = write(tmp_path, "backend/config/accounts.json", {
        "version": 2, "active_account": "SAME", "active_account_id": "PAPER-A",
        "runtime_generation": 1, "namespace_root": str(tmp_path / "accounts"),
        "accounts": {"PAPER-A": {"profile_name": "SAME"}, "PAPER-B": {"profile_name": "SAME"}},
    })
    report = audit(tmp_path)
    assert candidate(report, catalog)["format"] == "account_catalog_v2"
    for path in (global_path, new_path):
        assert candidate(report, path)["classification"] == "AMBIGUOUS"
    assert candidate(report, tmp_path / "accounts/PAPER-B/runtime-state.json")["exists"] is False
    assert report["selected_source"] is None


def test_r_orphan_evidence_and_temporary(tmp_path, states):
    evidence = {"version": 1, "generation": 1, "operation_id": "op", "stage": "STARTED",
                "pending_checksum": "unknown", "state": states[0]}
    path = write(tmp_path, "data/runtime/runtime-state-orphan.json.evidence.json", evidence)
    temporary = write(tmp_path, "data/runtime/runtime-state-other.json.tmp", seal(states[0], 2, "PENDING"))
    report = audit(tmp_path)
    for source in (path, temporary):
        row = candidate(report, source)
        assert row["orphaned"] is True and row["eligible"] is False


def test_s_relative_paths_are_workspace_relative(tmp_path, states, monkeypatch):
    path = write(tmp_path, "custom/state.json", seal(states[0], 1, "COMMITTED"))
    report = audit(tmp_path, state_paths=["custom/state.json"])
    elsewhere = tmp_path / "cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert audit(tmp_path, state_paths=["custom/state.json"]) == report
    assert candidate(report, path)["exists"]
    with pytest.raises(ValueError, match="absolute"):
        LegacyStateInventoryV2(workspace_root=".")


def fingerprint(root):
    return {str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
            for p in root.rglob("*") if p.is_file()}


def test_t_repeated_dry_runs_zero_writes_and_no_operational_calls(tmp_path, states, monkeypatch):
    from backend.services import durable_execution_state_v2 as durable
    from backend.services import runtime_context_v2
    from backend.services.startup_coordinator_v2 import StartupCoordinatorV2
    from backend.services.state_recovery_service_v2 import StateRecoveryServiceV2
    from backend.services.account_runtime_coordinator_v2 import AccountRuntimeCoordinatorV2
    from backend.connectors.paper_broker_connector_v2 import PaperBrokerConnectorV2
    from backend.services.execution_state_store_v2 import ExecutionStateStoreV2
    write(tmp_path, ASGI, seal(states[2], 7, "COMMITTED"))
    write(tmp_path, "backend/config/accounts.json", {"active_account": "A"})
    write(tmp_path, "data/risk_events.json", [{"timestamp": "2026-01-01T00:00:00Z", "account": "A"}])
    dbpath = tmp_path / "backend/storage/trades.db"
    dbpath.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(dbpath) as db:
        db.execute("CREATE TABLE trades (id INTEGER, order_id TEXT)")
    before = fingerprint(tmp_path)
    def denied(*args, **kwargs):
        raise AssertionError("dry-run attempted an operational mutation")
    with monkeypatch.context() as guard:
        guard.setattr(runtime_context_v2, "build_runtime_context", denied)
        for owner, names in (
            (Path, ("write_text", "write_bytes", "mkdir", "unlink", "rename", "replace")),
            (durable, ("atomic_write",)),
            (durable.DurableExecutionStateV2, ("acquire", "checkpoint", "_checkpoint", "record_evidence")),
            (ExecutionStateStoreV2, ("__init__", "capture_state", "restore_state", "save_to_file")),
            (StartupCoordinatorV2, ("startup_from", "startup_clean")),
            (StateRecoveryServiceV2, ("recover_from", "reconcile_pending_from")),
            (AccountRuntimeCoordinatorV2, ("start", "switch")),
            (PaperBrokerConnectorV2, ("__init__", "connect", "submit_order")),
        ):
            for name in names:
                guard.setattr(owner, name, denied)
        reports = [audit(tmp_path) for _ in range(3)]
    assert reports[0] == reports[1] == reports[2]
    assert fingerprint(tmp_path) == before
    assert all(row["classification"] != "SAFE_TO_MIGRATE" for row in reports[0]["candidates"])


def test_logical_aliases_hardlinks_and_identical_copies(tmp_path, states):
    path = write(tmp_path, ASGI, seal(states[0], 1, "COMMITTED"))
    link = tmp_path / CLI
    os.link(path, link)
    copy = write(tmp_path, "data/runtime/runtime-state-copy.json", seal(states[0], 1, "COMMITTED"))
    report = audit(tmp_path, state_paths=[ASGI, str(path), "data/runtime/../runtime/runtime-state-v2.json"])
    assert len([r for r in report["candidates"] if r["normalized_path"] == str(path)]) == 1
    assert any(set(group) == {str(path), str(link)} for group in report["physical_duplicates"])
    assert any(set(group) == {str(path), str(link), str(copy)} for group in report["content_duplicates"])


@pytest.mark.parametrize("payload", ['{', '{"schema_version":"2.0","schema_version":"2.0"}', '{"x":NaN}', '{"x":1e400}'])
def test_invalid_json_never_crashes_inventory(tmp_path, payload):
    path = tmp_path / ASGI
    path.parent.mkdir(parents=True)
    path.write_text(payload)
    assert candidate(audit(tmp_path), path)["classification"] == "CORRUPT"


@pytest.mark.parametrize("damage", ["checksum", "generation", "version", "identity", "records", "schema", "economic"])
def test_corruption_incompleteness_and_unsupported(tmp_path, states, damage):
    state = canonical(states[2])
    expected = "CORRUPT"
    if damage == "identity":
        state["account_identity"]["account_id"] = "PAPER-OTHER"
    if damage == "records":
        state.pop("execution_records")
        expected = "INCOMPLETE"
    if damage == "schema":
        state["schema_version"] = "1.0"
        expected = "UNSUPPORTED"
    if damage == "economic":
        state["execution_records"]["journal"][0]["pnl"] = 0.
    value = seal(state, 1, "COMMITTED")
    if damage == "checksum":
        value["checksum"] = "bad"
    if damage == "generation":
        value = seal(state, 0, "COMMITTED")
    if damage == "version":
        value["durability"]["version"] = 2
        value.pop("checksum")
        from backend.services.durable_execution_state_v2 import canonical as encode
        value["checksum"] = hashlib.sha256(encode(value)).hexdigest()
        expected = "UNSUPPORTED"
    path = write(tmp_path, ASGI, value)
    assert candidate(audit(tmp_path), path)["classification"] == expected


def test_old_variants_are_not_synthesized(tmp_path, states):
    value = deepcopy(states[0])
    value.pop("execution_records")
    path = write(tmp_path, ASGI, value)
    row = candidate(audit(tmp_path), path)
    assert row["classification"] == "INCOMPLETE"
    assert row["participants"]["journal"]["present"] is False
    value.pop("account_portfolio")
    write(tmp_path, ASGI, value)
    assert candidate(audit(tmp_path), path)["classification"] == "INCOMPLETE"


def test_pending_and_lock_are_never_eligible(tmp_path, states):
    value = {**states[0], "pending_operation": "op"}
    path = write(tmp_path, ASGI, seal(value, 1, "PENDING"))
    lock = Path(str(path) + ".lock")
    lock.write_bytes(b"0")
    row = candidate(audit(tmp_path), path)
    assert row["classification"] == "AMBIGUOUS"
    assert "PENDING" in row["open_activity"]["indicators"]
    assert str(lock) in row["related_artifacts"]


def test_changed_source_is_reported(tmp_path, states, monkeypatch):
    import backend.services.legacy_state_inventory_v2 as module
    path = write(tmp_path, ASGI, seal(states[0], 1, "COMMITTED"))
    original = module._read
    def changing(source):
        result = original(source)
        if source == path:
            source.write_text("changed")
        return result
    monkeypatch.setattr(module, "_read", changing)
    row = candidate(audit(tmp_path), path)
    assert row["classification"] == "INCOMPLETE"
    assert "source_changed_during_audit" in row["rejection_reasons"]


def test_cli_is_read_only_json_and_has_no_apply_mode(tmp_path):
    before = fingerprint(tmp_path)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "ARMS_RUNTIME_STATE_PATH": ""}
    result = subprocess.run([sys.executable, "-B", "-m", "backend.legacy_state_inventory_cli",
                             "--workspace", str(tmp_path)], capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["mode"] == "READ_ONLY_DRY_RUN"
    assert fingerprint(tmp_path) == before
    denied = subprocess.run([sys.executable, "-B", "-m", "backend.legacy_state_inventory_cli",
                             "--workspace", str(tmp_path), "--apply"], capture_output=True, text=True, env=env)
    assert denied.returncode == 2


@pytest.mark.parametrize("damage", [
    "broker_entry", "entry_quantity", "broker_quantity", "journal_entry", "broker_sl", "broker_tp",
    "closed_without_broker", "over_close", "economic_pnl", "daily_pnl", "missing_paper", "missing_oco",
])
def test_existing_semantic_contradictions_remain_blocked(tmp_path, damage):
    from backend.tests.test_recovery_consistency_v2 import snapshot, damage_state
    value = snapshot("full" if damage in {"closed_without_broker", "over_close", "economic_pnl"} else "open")
    damage_state(value, damage)
    path = write(tmp_path, ASGI, seal(value, 1, "COMMITTED"))
    row = candidate(audit(tmp_path), path)
    assert row["classification"] == "CORRUPT", row
    assert row["eligible"] is False


def test_os_audit_hook_denies_every_write_and_disk_sqlite(tmp_path, states):
    write(tmp_path, ASGI, seal(states[2], 4, "COMMITTED"))
    dbpath = tmp_path / "backend/storage/trades.db"
    dbpath.parent.mkdir(parents=True)
    with sqlite3.connect(dbpath) as db:
        db.execute("CREATE TABLE trades (id INTEGER)")
    before = fingerprint(tmp_path)
    script = """
import json, os, sys
def deny_mutation(event, args):
    if event == 'open':
        mode, flags = args[1], args[2]
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            raise AssertionError('write open denied')
    if event in {'os.mkdir','os.remove','os.rename','os.rmdir','os.chmod','os.link','os.symlink','os.truncate','socket.__new__'}:
        raise AssertionError('mutation denied: '+event)
    if event == 'sqlite3.connect' and args[0] != ':memory:':
        raise AssertionError('disk sqlite denied')
sys.addaudithook(deny_mutation)
from backend.services.legacy_state_inventory_v2 import LegacyStateInventoryV2
report=LegacyStateInventoryV2(workspace_root=sys.argv[1],environment={}).dry_run()
print(json.dumps(report))
"""
    result = subprocess.run([sys.executable, "-B", "-c", script, str(tmp_path)], capture_output=True,
                            text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert candidate(report, dbpath)["format"] == "legacy_sqlite_journal"
    assert fingerprint(tmp_path) == before


def test_unrealized_pnl_must_match_portfolio(tmp_path, states):
    value = deepcopy(states[1])
    account = value["account_portfolio"]["account"]["state"]
    account["unrealized_pnl"] += 10
    account["total_pnl"] += 10
    account["equity"] += 10
    account["peak_equity"] += 10
    path = write(tmp_path, ASGI, seal(value, 1, "COMMITTED"))
    assert candidate(audit(tmp_path), path)["classification"] == "CORRUPT"


def test_database_sidecars_are_reported_without_replay(tmp_path):
    path = tmp_path / "backend/storage/trades.db"
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as database:
        database.execute("CREATE TABLE trades (id INTEGER)")
    sidecar = Path(str(path) + "-wal")
    sidecar.write_bytes(b"unresolved")
    row = candidate(audit(tmp_path), path)
    assert row["classification"] == "INCOMPLETE"
    assert str(sidecar) in row["related_artifacts"]


def test_auxiliary_and_generic_orphan_files(tmp_path):
    write(tmp_path, "data/risk_events.json", [{"timestamp": "2026-01-01T00:00:00Z", "account": "A"}])
    write(tmp_path, "data/trade_plans.jsonl", {"created_at": "2026-01-01T00:00:00Z"})
    write(tmp_path, "data/simulated_trades.jsonl", {"opened_at": "2026-01-01T00:00:00Z"})
    csvpath = tmp_path / "data/reports/trade_journal.csv"
    csvpath.parent.mkdir()
    csvpath.write_text("opened_at,closed_at,pnl\n")
    orphan = write(tmp_path, "data/orphan.json.tmp", {"incomplete": True})
    row = candidate(audit(tmp_path), orphan)
    assert row["orphaned"] and row["eligible"] is False
    report = audit(tmp_path)
    assert all(row["classification"] != "SAFE_TO_MIGRATE" for row in report["candidates"])


def test_hash_still_reported_when_parse_budget_exceeded(tmp_path, states, monkeypatch):
    import backend.services.legacy_state_inventory_v2 as module
    path = write(tmp_path, ASGI, seal(states[0], 1, "COMMITTED"))
    monkeypatch.setattr(module, "MAX_PARSE_BYTES", 8)
    row = candidate(audit(tmp_path), path)
    assert row["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert row["classification"] == "UNSUPPORTED"


def test_permission_error_does_not_hide_candidate(tmp_path, states, monkeypatch):
    import backend.services.legacy_state_inventory_v2 as module
    path = write(tmp_path, ASGI, seal(states[0], 1, "COMMITTED"))
    original = module._read
    def read(source):
        if source == path:
            raise PermissionError("denied")
        return original(source)
    monkeypatch.setattr(module, "_read", read)
    row = candidate(audit(tmp_path), path)
    assert row["exists"] is True and row["classification"] == "INCOMPLETE"


def test_malicious_catalog_path_is_not_followed(tmp_path):
    write(tmp_path, "backend/config/accounts.json", {
        "version": 2, "active_account": "A", "namespace_root": str(tmp_path / "accounts"),
        "accounts": {"../escape": {"profile_name": "A"}},
    })
    report = audit(tmp_path)
    assert report["discovery_errors"]
    assert not any("escape" in row["normalized_path"] for row in report["candidates"])


def test_unreadable_scan_directory_is_explicit(tmp_path, monkeypatch):
    import backend.services.legacy_state_inventory_v2 as module
    (tmp_path / "data").mkdir()
    original = module.os.walk
    def walk(top, **kwargs):
        if Path(top) == tmp_path / "data":
            kwargs["onerror"](PermissionError("denied"))
            return iter(())
        return original(top, **kwargs)
    monkeypatch.setattr(module.os, "walk", walk)
    report = audit(tmp_path)
    assert report["discovery_errors"] == [{"source": str(tmp_path / "data"), "reason": "directory_scan_failed"}]


def test_only_designated_environment_variable_is_read(tmp_path):
    class RestrictedEnvironment:
        def get(self, key, default=None):
            assert key == "ARMS_RUNTIME_STATE_PATH"
            return ""
        def __iter__(self):
            raise AssertionError("must not enumerate unrelated environment variables")
    report = LegacyStateInventoryV2(workspace_root=tmp_path, environment=RestrictedEnvironment()).dry_run()
    assert report["migration_enabled"] is False


def test_windows_stat_ctime_difference_is_not_a_content_change(tmp_path, monkeypatch):
    if os.name != "nt":
        pytest.skip("Windows stat/fstat compatibility")
    from types import SimpleNamespace
    import backend.services.legacy_state_inventory_v2 as module
    path = tmp_path / "state.json"
    path.write_bytes(b"{}")
    original = module.os.fstat
    def fstat(fd):
        actual = original(fd)
        return SimpleNamespace(st_dev=actual.st_dev, st_ino=actual.st_ino, st_size=actual.st_size,
                               st_mode=actual.st_mode, st_mtime_ns=actual.st_mtime_ns, st_ctime_ns=actual.st_ctime_ns+1000)
    monkeypatch.setattr(module.os, "fstat", fstat)
    assert module._read(path)[3] is True


@pytest.mark.parametrize("stage", ["PREPARED", "STARTED", "OBSERVED", "COMPLETED"])
def test_review_valid_evidence_retains_its_envelope(tmp_path, states, stage):
    from backend.services.durable_execution_state_v2 import canonical as encode
    evidence = {"version": 1, "generation": 2, "operation_id": "operation",
                "pending_checksum": "a" * 64, "stage": stage, "state": states[0]}
    evidence["checksum"] = hashlib.sha256(encode(evidence)).hexdigest()
    path = write(tmp_path, ASGI + ".evidence.json", evidence)
    row = candidate(audit(tmp_path), path)
    assert row["classification"] == "AMBIGUOUS", row
    assert row["checksum"] == {"present": True, "valid": True}
    assert row["validation_results"] == {"structural": "PASS", "semantic": "PASS", "economic": "PASS"}
    assert row["durability"]["stage"] == stage
    assert row["eligible"] is False and row["potential_destination"] is None


@pytest.mark.parametrize("source", ["huge_integer", "wide_csv"])
def test_review_parser_limits_do_not_abort_inventory(tmp_path, states, source):
    if source == "huge_integer":
        state = deepcopy(states[0])
        state["account_portfolio"]["account"]["state"]["balance"] = 10 ** 500
        path = write(tmp_path, ASGI, seal(state, 1, "COMMITTED"))
        expected = "CORRUPT"
    else:
        path = tmp_path / "data/reports/trade_journal.csv"
        path.parent.mkdir(parents=True)
        path.write_text("x" * 150000)
        expected = "UNSUPPORTED"
    other = write(tmp_path, CLI, seal(states[0], 1, "COMMITTED"))
    before = fingerprint(tmp_path)
    report = audit(tmp_path)
    assert candidate(report, path)["classification"] == expected
    assert candidate(report, other)["classification"] == "AMBIGUOUS"
    assert fingerprint(tmp_path) == before


@pytest.mark.parametrize("damage", [
    "journal_status", "remaining_quantity", "live_fill", "live_order", "target_type", "history_pnl",
])
def test_review_structural_contradictions_cannot_report_pass(tmp_path, states, damage):
    state = deepcopy(states[2] if damage == "history_pnl" else states[1])
    records = state["execution_records"]
    if damage == "journal_status":
        records["journal"][0]["status"] = "CLOSED"
    elif damage == "remaining_quantity":
        records["journal"][0]["remaining_quantity"] = 999
    elif damage == "live_fill":
        records["paper"]["fills"][0]["execution_mode"] = "LIVE"
    elif damage == "live_order":
        next(iter(records["paper"]["orders"].values()))["execution_mode"] = "LIVE"
    elif damage == "target_type":
        state["account_portfolio"]["account"]["state"]["target_reached"] = "yes"
    else:
        records["history"][0]["realized_pnl"] += 1
    path = write(tmp_path, ASGI, seal(state, 1, "COMMITTED"))
    row = candidate(audit(tmp_path), path)
    assert row["classification"] == "CORRUPT"
    assert row["validation_results"]["structural"] == "FAIL"
    assert row["eligible"] is False


def test_review_runtime_and_durable_state_unchanged_by_inventory(tmp_path):
    lifecycle, account, store, _, startup = build_runtime()
    path = tmp_path / ASGI
    startup.startup_from(file_path=path)
    try:
        open_position(lifecycle)
        write(tmp_path, "backend/config/accounts.json", {"active_account": "A"})
        write(tmp_path, "data/risk_events.json", [{"account": "A", "timestamp": "2026-01-01T00:00:00Z"}])
        def operational():
            value = store.capture_state()
            value.pop("captured_at")
            return {"snapshot": value, "generation": store._durability.generation,
                    "account": account.get_state(), "records": store._capture_records()}
        def persisted():
            return {str(p): (p.stat().st_size, p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
                    for p in tmp_path.rglob("*") if p.is_file() and p.suffix != ".lock"}
        before = operational()
        files_before = persisted()
        reports = [audit(tmp_path) for _ in range(3)]
        assert reports[0] == reports[1] == reports[2]
        assert operational() == before
        assert persisted() == files_before
    finally:
        store._durability.release()
