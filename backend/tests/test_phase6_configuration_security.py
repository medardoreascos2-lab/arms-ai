"""R74B fail-closed configuration security scan tests."""

import json
from pathlib import Path

from backend.phase6.config_security import scan_phase6_configuration


ROOT = Path(__file__).parents[2]
IAC_ROOT = ROOT / "infra" / "phase6" / "aws"
DEPLOYMENT_ROOT = ROOT / "deploy" / "phase6" / "aws"


def test_phase6_configuration_passes_all_required_security_checks():
    report = scan_phase6_configuration(IAC_ROOT, DEPLOYMENT_ROOT)

    assert report.passed, report.findings
    assert report.status == "PASS"
    assert report.files_scanned == 30
    assert report.external_actions_performed is False


def test_manifest_scan_blocks_authority_debug_public_network_and_plaintext_secret(tmp_path):
    iac = tmp_path / "iac"
    deploy = tmp_path / "deploy"
    iac.mkdir()
    deploy.mkdir()
    document = {
        "environment": "production",
        "network": {"assign_public_ip": True, "egress_to": ["internet"]},
        "configuration": {
            "ARMS_DEBUG": "true",
            "ARMS_LIVE_ENABLED": "true",
            "ARMS_BROKER_PASSWORD": "plaintext",
        },
        "authority": {"broker": True, "paper": False, "live": True, "production": True},
    }
    (deploy / "unsafe.json").write_text(json.dumps(document), encoding="utf-8")
    (iac / "unsafe.tf").write_text(
        'resource "aws_db_instance" "unsafe" { publicly_accessible = true }\n'
        'resource "aws_vpc_security_group_ingress_rule" "unsafe" { cidr_ipv4 = "0.0.0.0/0" }\n',
        encoding="utf-8",
    )

    report = scan_phase6_configuration(iac, deploy)
    codes = {finding.code for finding in report.findings}

    assert report.status == "BLOCKED"
    assert {
        "NON_STAGING_ENVIRONMENT",
        "PUBLIC_WORKLOAD_IP",
        "UNRESTRICTED_EGRESS",
        "DEBUG_ENABLED",
        "EXECUTION_AUTHORITY_ENABLED",
        "PLAINTEXT_SECRET_FIELD",
        "BROKER_CREDENTIAL_PRESENT",
        "OPEN_INGRESS",
        "PUBLIC_DATABASE",
    }.issubset(codes)


def test_secret_references_are_allowed_but_values_and_invalid_json_fail_closed(tmp_path):
    iac = tmp_path / "iac"
    deploy = tmp_path / "deploy"
    iac.mkdir()
    deploy.mkdir()
    safe = {
        "environment": "staging",
        "secret_references": [
            {"name": "ARMS_DATABASE_CREDENTIAL", "value_from": "{{DATABASE_SECRET_ARN}}"}
        ],
        "authority": {"broker": False, "paper": False, "live": False, "production": False},
    }
    (deploy / "safe.json").write_text(json.dumps(safe), encoding="utf-8")
    (iac / "main.tf").write_text("locals { staging = true }\n", encoding="utf-8")

    safe_report = scan_phase6_configuration(iac, deploy)
    assert safe_report.passed, safe_report.findings

    (deploy / "broken.json").write_text("{", encoding="utf-8")
    blocked = scan_phase6_configuration(iac, deploy)
    assert blocked.status == "BLOCKED"
    assert any(finding.code == "INVALID_CONFIGURATION" for finding in blocked.findings)


def test_tfvars_files_are_rejected_without_reading_or_exposing_values(tmp_path):
    iac = tmp_path / "iac"
    deploy = tmp_path / "deploy"
    iac.mkdir()
    deploy.mkdir()
    (iac / "main.tf").write_text("locals { staging = true }\n", encoding="utf-8")
    (iac / "unsafe.tfvars").write_text("opaque", encoding="utf-8")
    (deploy / "manifest.json").write_text(
        json.dumps({"environment": "staging", "authority": {"live": False}}),
        encoding="utf-8",
    )

    report = scan_phase6_configuration(iac, deploy)

    assert report.status == "BLOCKED"
    assert any(finding.code == "PLAINTEXT_VARIABLE_VALUES" for finding in report.findings)
