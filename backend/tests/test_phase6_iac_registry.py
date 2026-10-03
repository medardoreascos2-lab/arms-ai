"""R71H static checks for the private staging artifact registry."""

from pathlib import Path


ROOT = Path(__file__).parents[2]
REGISTRY = ROOT / "infra" / "phase6" / "aws" / "modules" / "registry"


def _text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(REGISTRY.glob("*.tf")))


def test_registry_is_encrypted_immutable_private_and_scanned():
    text = _text()

    assert 'image_tag_mutability = "IMMUTABLE"' in text
    assert "force_delete         = false" in text
    assert 'encryption_type = "KMS"' in text
    assert "enable_key_rotation     = true" in text
    assert "scan_on_push = true" in text
    assert 'DeploymentReferences = "digest-only"' in text


def test_release_gate_requires_digest_scan_signature_and_provenance():
    text = _text()

    assert "digest_only_deployment     = true" in text
    assert "maximum_critical_findings  = 0" in text
    assert "maximum_high_findings      = 0" in text
    assert "signature_required         = true" in text
    assert "provenance_required        = true" in text
    assert "external_upload_authorized = false" in text


def test_registry_retention_is_bounded_and_repository_is_not_force_deleted():
    text = _text()

    assert 'countType   = "imageCountMoreThan"' in text
    assert "countNumber = var.retained_image_count" in text
    assert "var.retained_image_count >= 5 && var.retained_image_count <= 100" in text
    assert "force_delete         = false" in text


def test_publish_and_pull_policies_are_separate_and_repository_scoped():
    text = _text()

    assert 'resource "aws_iam_policy" "publisher"' in text
    assert 'resource "aws_iam_policy" "puller"' in text
    assert '"ecr:PutImage"' in text
    assert '"ecr:BatchGetImage"' in text
    assert text.count("Resource = aws_ecr_repository.staging.arn") == 2
    assert "ecr:DeleteRepository" not in text
    assert "ecr:SetRepositoryPolicy" not in text
