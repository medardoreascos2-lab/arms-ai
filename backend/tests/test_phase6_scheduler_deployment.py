"""R72C contract tests for the leader-elected staging scheduler."""

import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
PATH = ROOT / "deploy" / "phase6" / "aws" / "scheduler.workload.json"


def _manifest():
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_scheduler_runs_two_candidates_with_exactly_one_owner_per_job():
    workload = _manifest()["workload"]
    election = workload["leader_election"]

    assert workload["replicas"] == {"desired": 2, "minimum": 2, "maximum": 2}
    assert election["store"] == "postgresql"
    assert election["maximum_owners_per_job"] == 1
    assert election["database_clock_required"] is True
    assert election["monotonic_fencing_token_required"] is True
    assert election["compare_and_swap_required"] is True
    assert election["stale_owner_may_not_commit"] is True
    assert election["heartbeat_seconds"] < election["lease_seconds"]


def test_scheduler_only_dispatches_idempotent_durable_outbox_work():
    dispatch = _manifest()["workload"]["dispatch"]

    assert dispatch["mode"] == "durable-outbox-only"
    assert dispatch["direct_effects_allowed"] is False
    assert dispatch["duplicate_dispatch_allowed"] is False
    assert dispatch["idempotency_key"] == "environment:job_name:scheduled_at"
    assert {job["queue"] for job in dispatch["jobs"]} <= {
        "maintenance", "operational-outbox", "research"
    }


def test_scheduler_fails_closed_on_database_or_secret_unavailability():
    health = _manifest()["workload"]["health"]

    assert health["database_unavailable_state"] == "BLOCKED"
    assert health["secret_unavailable_state"] == "BLOCKED"
    assert health["lease_loss_state"] == "READY_NON_OWNER"


def test_scheduler_has_zero_financial_execution_authority():
    manifest = _manifest()
    config = manifest["workload"]["configuration"]

    assert set(manifest["authority"].values()) == {False}
    for name in (
        "ARMS_EXECUTION_AUTHORIZED",
        "ARMS_BROKER_ENABLED",
        "ARMS_PAPER_ENABLED",
        "ARMS_LIVE_ENABLED",
        "ARMS_PRODUCTION_MUTATION_AUTHORIZED",
    ):
        assert config[name] == "false"
