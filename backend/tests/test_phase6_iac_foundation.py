"""R71A checks for the non-provisioning Phase 6 IaC foundation."""

from pathlib import Path
import re


ROOT = Path(__file__).parents[2]
IAC_ROOT = ROOT / "infra" / "phase6" / "aws"


def _terraform_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(IAC_ROOT.glob("*.tf"))
    )


def test_foundation_is_staging_only_and_has_zero_resources():
    text = _terraform_text()

    assert 'condition     = var.environment == "staging"' in text
    assert 'Authority   = "no-broker-no-live-no-production"' in text
    assert re.search(r'^resource\s+"', text, flags=re.MULTILINE) is None
    assert re.search(r'^\s*backend\s+"', text, flags=re.MULTILINE) is None


def test_foundation_requires_governance_tags_and_no_secret_inputs():
    text = _terraform_text()

    for field in ("Application", "Environment", "ManagedBy", "Authority", "Owner", "CostCenter"):
        assert field in text
    assert 'variable "aws_region"' in text
    assert 'variable "owner"' in text
    assert 'variable "cost_center"' in text
    assert re.search(r'variable\s+"[^\"]*(password|secret|token|credential)', text, re.I) is None


def test_foundation_documents_all_authority_boundaries():
    readme = (IAC_ROOT / "README.md").read_text(encoding="utf-8")

    for token in (
        "EXTERNAL_RESOURCES_CREATED=FALSE",
        "BROKER_AUTHORITY=FALSE",
        "PAPER_AUTHORITY=FALSE",
        "LIVE_AUTHORITY=FALSE",
        "PRODUCTION_DEPLOYMENT_AUTHORITY=FALSE",
    ):
        assert token in readme
