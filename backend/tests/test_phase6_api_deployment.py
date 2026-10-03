"""R72A contract tests for the external staging API manifest."""

import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST_PATH = ROOT / "deploy" / "phase6" / "aws" / "api.workload.json"


def _manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_api_is_multi_replica_private_bounded_and_digest_pinned():
    workload = _manifest()["workload"]

    assert workload["kind"] == "ecs-fargate-service"
    assert workload["replicas"] == {
        "desired": 2,
        "minimum": 2,
        "maximum": 4,
        "availability_zones": 2,
    }
    assert workload["image"]["uri"].endswith("@{{IMAGE_DIGEST}}")
    assert all(workload["image"][gate] is True for gate in (
        "digest_required", "signature_required", "provenance_required", "scan_gate_required"
    ))
    assert workload["runtime"]["cpu_units"] == 512
    assert workload["runtime"]["memory_mib"] == 1024
    assert workload["network"]["assign_public_ip"] is False


def test_api_authentication_and_secret_reference_are_required_without_values():
    workload = _manifest()["workload"]
    config = workload["configuration"]

    assert config["ARMS_AUTH_REQUIRED"] == "true"
    for name in ("ARMS_OIDC_ISSUER", "ARMS_OIDC_AUDIENCE", "ARMS_OIDC_JWKS_URI"):
        assert config[name].startswith("{{") and config[name].endswith("}}")
    assert workload["secret_references"] == [{
        "name": "ARMS_DATABASE_CREDENTIAL",
        "value_from": "{{APPLICATION_DATABASE_SECRET_ARN}}",
    }]
    serialized = MANIFEST_PATH.read_text(encoding="utf-8").lower()
    assert '"password"' not in serialized
    assert '"api_key"' not in serialized


def test_api_health_and_readiness_are_read_only_and_dependency_aware():
    health = _manifest()["workload"]["health"]

    assert health["liveness"]["method"] == "GET"
    assert health["readiness"]["method"] == "GET"
    assert health["liveness"]["side_effects_allowed"] is False
    assert health["readiness"]["side_effects_allowed"] is False
    assert health["readiness"]["required_dependencies"] == [
        "database", "secret_provider", "identity_jwks"
    ]


def test_api_manifest_has_zero_trading_and_production_authority():
    manifest = _manifest()
    config = manifest["workload"]["configuration"]

    assert set(manifest["authority"].values()) == {False}
    assert config["ARMS_EXECUTION_AUTHORIZED"] == "false"
    assert config["ARMS_BROKER_ENABLED"] == "false"
    assert config["ARMS_PAPER_ENABLED"] == "false"
    assert config["ARMS_LIVE_ENABLED"] == "false"
    assert config["ARMS_PRODUCTION_MUTATION_AUTHORIZED"] == "false"
