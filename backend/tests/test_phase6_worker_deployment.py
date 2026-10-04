"""R72B contract tests for separated staging workers."""

import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
PATH = ROOT / "deploy" / "phase6" / "aws" / "workers.workload.json"


def _manifest():
    return json.loads(PATH.read_text(encoding="utf-8"))


def _by_name():
    return {item["name"]: item for item in _manifest()["workloads"]}


def test_worker_types_have_separate_identities_queues_and_resource_limits():
    workloads = _by_name()

    assert set(workloads) == {"outbox-worker", "research-worker", "maintenance-worker"}
    assert len({item["identity"]["task_role_arn"] for item in workloads.values()}) == 3
    assert len({item["queue"]["name"] for item in workloads.values()}) == 3
    assert workloads["outbox-worker"]["resources"] == {"cpu_units": 512, "memory_mib": 1024}
    assert workloads["research-worker"]["resources"] == {"cpu_units": 1024, "memory_mib": 2048}
    assert workloads["maintenance-worker"]["resources"] == {"cpu_units": 256, "memory_mib": 512}
    assert all(item["identity"]["shared_role_allowed"] is False for item in workloads.values())


def test_operational_worker_has_bounded_retries_dead_letter_and_fencing():
    worker = _by_name()["outbox-worker"]

    assert worker["replicas"]["minimum"] == 2
    assert worker["queue"]["maximum_in_flight_per_replica"] == 8
    assert worker["queue"]["maximum_attempts"] == 5
    assert worker["queue"]["dead_letter_required"] is True
    assert worker["queue"]["tenant_scope_required"] is True
    assert worker["supervision"]["fencing_token_required"] is True


def test_research_starts_at_zero_and_cannot_consume_operational_queue():
    research = _by_name()["research-worker"]

    assert research["replicas"] == {"desired": 0, "minimum": 0, "maximum": 2}
    assert research["queue"]["instrument_scope_required"] is True
    assert research["configuration"]["ARMS_SYNTHETIC_DATA_ONLY"] == "true"
    assert research["configuration"]["ARMS_OPERATIONAL_QUEUE_ACCESS"] == "false"
    assert research["secret_references"] == [{
        "name": "ARMS_RESEARCH_DATABASE_CREDENTIAL",
        "value_from": "{{RESEARCH_DATABASE_SECRET_ARN}}",
    }]


def test_maintenance_is_single_concurrency_read_only_and_secret_free():
    maintenance = _by_name()["maintenance-worker"]

    assert maintenance["replicas"]["maximum"] == 1
    assert maintenance["queue"]["maximum_in_flight_per_replica"] == 1
    assert maintenance["configuration"]["ARMS_DATABASE_WRITE_ALLOWED"] == "false"
    assert maintenance["configuration"]["ARMS_EXTERNAL_SIDE_EFFECTS_ALLOWED"] == "false"
    assert maintenance["secret_references"] == []


def test_all_workers_have_zero_execution_authority():
    manifest = _manifest()
    assert set(manifest["shared"]["authority"].values()) == {False}

    for worker in manifest["workloads"]:
        config = worker["configuration"]
        for name in (
            "ARMS_EXECUTION_AUTHORIZED",
            "ARMS_BROKER_ENABLED",
            "ARMS_PAPER_ENABLED",
            "ARMS_LIVE_ENABLED",
            "ARMS_PRODUCTION_MUTATION_AUTHORIZED",
        ):
            assert config[name] == "false"
