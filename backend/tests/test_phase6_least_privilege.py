"""R76B least-privilege checks across every Phase 6 service boundary."""

from pathlib import Path
import shutil

from backend.phase6.least_privilege import REQUIRED_SURFACES, validate_phase6_least_privilege


ROOT = Path(__file__).parents[2]
IAC_ROOT = ROOT / "infra" / "phase6" / "aws"
DEPLOYMENT_ROOT = ROOT / "deploy" / "phase6" / "aws"


def test_phase6_templates_enforce_least_privilege_on_all_required_surfaces():
    report = validate_phase6_least_privilege(IAC_ROOT, DEPLOYMENT_ROOT)

    assert report.passed, report.findings
    assert report.status == "PASS"
    assert report.surfaces == REQUIRED_SURFACES
    assert set(report.surfaces) == {
        "API",
        "workers",
        "scheduler",
        "DB",
        "secret manager",
        "backup",
        "artifact registry",
        "telemetry",
    }
    assert report.external_actions_performed is False


def test_broad_admin_or_service_permission_blocks_validation(tmp_path):
    iac = tmp_path / "iac"
    deploy = tmp_path / "deploy"
    shutil.copytree(IAC_ROOT, iac)
    shutil.copytree(DEPLOYMENT_ROOT, deploy)
    identity = iac / "modules" / "identity" / "main.tf"
    identity.write_text(
        identity.read_text(encoding="utf-8")
        + '\nresource "aws_iam_policy" "unsafe" { policy = "AdministratorAccess" }\n'
        + 'locals { unsafe_action = "iam:*" }\n',
        encoding="utf-8",
    )

    report = validate_phase6_least_privilege(iac, deploy)
    codes = {finding.code for finding in report.findings}

    assert report.status == "BLOCKED"
    assert "BROAD_ADMIN_PERMISSION" in codes
    assert "BROAD_SERVICE_PERMISSION" in codes


def test_shared_or_duplicate_workload_roles_block_validation(tmp_path):
    iac = tmp_path / "iac"
    deploy = tmp_path / "deploy"
    shutil.copytree(IAC_ROOT, iac)
    shutil.copytree(DEPLOYMENT_ROOT, deploy)
    api = deploy / "api.workload.json"
    text = api.read_text(encoding="utf-8")
    text = text.replace('"shared_role_allowed": false', '"shared_role_allowed": true')
    text = text.replace("{{API_EXECUTION_ROLE_ARN}}", "{{API_TASK_ROLE_ARN}}")
    api.write_text(text, encoding="utf-8")

    report = validate_phase6_least_privilege(iac, deploy)
    codes = {finding.code for finding in report.findings}

    assert report.status == "BLOCKED"
    assert "SHARED_ROLE_ENABLED" in codes
    assert "DUPLICATE_ROLE_REFERENCE" in codes


def test_backup_writer_and_restore_reader_remain_separate():
    backup = (IAC_ROOT / "modules" / "backup" / "main.tf").read_text(encoding="utf-8")
    writer, reader = backup.split('resource "aws_iam_policy" "restore_reader"', 1)

    assert '"s3:PutObject"' in writer
    assert '"s3:GetObject"' not in writer
    assert '"s3:GetObject"' in reader
    assert '"s3:PutObject"' not in reader
