"""R72D tests for operational capacity protection from research work."""

import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
PATH = ROOT / "deploy" / "phase6" / "aws" / "research-isolation.policy.json"


def _policy():
    return json.loads(PATH.read_text(encoding="utf-8"))["policy"]


def test_operational_capacity_is_reserved_before_research_capacity():
    policy = _policy()
    reserve = policy["operational_reserve"]
    research = policy["research_budget"]

    assert policy["priority_order"][:3] == ["api", "operational-worker", "scheduler"]
    assert policy["priority_order"][-1] == "research"
    assert reserve["api_minimum_replicas"] == 2
    assert reserve["worker_minimum_replicas"] == 2
    assert reserve["scheduler_minimum_replicas"] == 2
    assert research["desired_replicas"] == 0
    assert research["maximum_cpu_units"] == (
        research["maximum_replicas"] * research["cpu_units_per_replica"]
    )
    assert research["maximum_memory_mib"] == (
        research["maximum_replicas"] * research["memory_mib_per_replica"]
    )


def test_research_concurrency_queue_database_and_runtime_are_bounded():
    budget = _policy()["research_budget"]

    assert 0 < budget["global_concurrency"] <= budget["maximum_replicas"]
    assert budget["per_tenant_concurrency"] == 1
    assert budget["per_instrument_concurrency"] == 1
    assert budget["database_connections"] == 10
    assert budget["maximum_queue_depth"] == 50
    assert budget["maximum_payload_mib"] == 16
    assert budget["maximum_runtime_seconds"] == 3600


def test_research_cannot_consume_operational_queue_or_storage_authority():
    policy = _policy()
    queue = policy["queue_isolation"]
    storage = policy["storage_isolation"]

    assert queue["research_queue"] != queue["operational_queue"]
    assert queue["cross_queue_consumption_allowed"] is False
    assert queue["instrument_scope_required"] is True
    assert queue["tenant_scope_required"] is True
    assert queue["explicit_aggregation_label_required"] is True
    assert storage["backup_prefix_access"] is False
    assert storage["operational_outbox_write"] is False
    assert storage["operational_audit_mutation"] is False


def test_backpressure_sheds_or_pauses_research_without_operational_mutation():
    backpressure = _policy()["backpressure"]

    assert backpressure["queue_full_action"] == "REJECT_WITHOUT_SIDE_EFFECTS"
    assert backpressure["operational_pressure_action"] == "SCALE_RESEARCH_TO_ZERO"
    assert backpressure["database_pool_pressure_action"] == "PAUSE_RESEARCH_DEQUEUE"
    assert backpressure["telemetry_unavailable_action"] == "PAUSE_NEW_RESEARCH"
    assert backpressure["shed_order"] == ["queued-research", "running-research"]


def test_research_policy_has_zero_trading_authority_and_synthetic_only_data():
    safety = _policy()["safety"]

    assert safety.pop("synthetic_data_only") is True
    assert set(safety.values()) == {False}
