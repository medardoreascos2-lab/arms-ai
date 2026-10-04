"""R71E static checks for external identity and service-role boundaries."""

from pathlib import Path
import re


ROOT = Path(__file__).parents[2]
IDENTITY = ROOT / "infra" / "phase6" / "aws" / "modules" / "identity"


def _text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(IDENTITY.glob("*.tf")))


def test_external_oidc_contract_requires_https_issuer_audience_and_jwks():
    text = _text()

    assert 'variable "oidc_issuer"' in text
    assert 'variable "oidc_audience"' in text
    assert 'variable "oidc_jwks_uri"' in text
    assert text.count('can(regex("^https://') == 2
    assert 'allowed_algorithms        = ["RS256", "ES256"]' in text
    assert 'reject_unknown_key_ids    = true' in text
    assert 'tenant_created            = false' in text
    assert 'resource "aws_cognito_' not in text
    assert 'resource "aws_iam_openid_connect_provider"' not in text


def test_required_tenant_role_and_standard_claims_are_fail_closed():
    text = _text()

    for claim in ("sub", "iss", "aud", "iat", "exp"):
        assert f'"{claim}"' in text
    assert "var.tenant_claim" in text
    assert "var.role_claim" in text
    assert 'reject_missing_tenant     = true' in text
    assert 'reject_missing_role       = true' in text
    assert 'key_rotation_max_age_days >= 7' in text


def test_service_identities_are_separate_and_assumable_only_by_ecs_tasks():
    text = _text()

    for identity in (
        "api", "worker", "scheduler", "research", "migration", "maintenance", "backup",
        "restore", "telemetry", "artifact-publisher",
    ):
        assert f'"{identity}"' in text
    assert 'identifiers = ["ecs-tasks.amazonaws.com"]' in text
    assert 'actions = ["sts:AssumeRole"]' in text
    assert "AdministratorAccess" not in text
    assert re.search(r'Action\s*=\s*"\*"', text) is None


def test_secret_reader_policies_attach_only_to_the_four_declared_consumers():
    text = _text()

    assert 'toset(["api", "worker", "scheduler", "research"])' in text
    assert 'aws_iam_role.service[each.key].name' in text
    assert 'policy_arn = each.value' in text


def test_role_mapping_has_no_execution_or_production_permission():
    text = _text().lower()

    assert "staging:read" in text
    assert "research:submit" in text
    assert "trade:execute" not in text
    assert "live:" not in text
    assert "production:" not in text
