"""R74A offline static parser and schema checks for Phase 6 IaC."""

from pathlib import Path

from backend.phase6.iac_static_validation import REQUIRED_MODULES, validate_iac_tree


ROOT = Path(__file__).parents[2]
IAC_ROOT = ROOT / "infra" / "phase6" / "aws"


def test_phase6_iac_passes_credential_free_static_validation():
    report = validate_iac_tree(IAC_ROOT)

    assert report.passed, report.errors
    assert report.terraform_file_count == 26
    assert set(report.module_names) == REQUIRED_MODULES
    assert report.native_validation_available is False
    assert report.external_actions_performed is False
    assert any("provider schema" in limitation for limitation in report.limitations)


def test_validator_reports_missing_foundation_and_modules(tmp_path):
    root = tmp_path / "iac"
    root.mkdir()

    report = validate_iac_tree(root)

    assert report.passed is False
    assert any("missing root" in error for error in report.errors)
    assert any("missing required modules" in error for error in report.errors)


def test_validator_reports_unbalanced_hcl_without_running_provider_tools(tmp_path):
    root = tmp_path / "iac"
    root.mkdir()
    for name in ("providers.tf", "variables.tf", "locals.tf", "outputs.tf"):
        (root / name).write_text("", encoding="utf-8")
    (root / "versions.tf").write_text(
        'terraform { required_version = ">= 1.6"\n'
        'required_providers { aws = { source  = "hashicorp/aws" } }\n',
        encoding="utf-8",
    )

    report = validate_iac_tree(root)

    assert report.passed is False
    assert any("unclosed delimiter" in error for error in report.errors)
    assert report.external_actions_performed is False


def test_validator_reports_duplicate_declarations(tmp_path):
    root = tmp_path / "iac"
    root.mkdir()
    for name in ("providers.tf", "variables.tf", "locals.tf", "outputs.tf"):
        (root / name).write_text('', encoding="utf-8")
    (root / "versions.tf").write_text(
        'terraform { required_version = ">= 1.6"\n'
        'required_providers { aws = { source  = "hashicorp/aws" } } }\n'
        'output "same" { value = true }\n',
        encoding="utf-8",
    )
    (root / "outputs.tf").write_text('output "same" { value = false }\n', encoding="utf-8")

    report = validate_iac_tree(root)

    assert report.passed is False
    assert any("duplicate output declaration" in error for error in report.errors)
