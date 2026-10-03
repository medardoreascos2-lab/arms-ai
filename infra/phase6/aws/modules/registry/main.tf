resource "aws_kms_key" "registry" {
  description             = "ARMS AI staging OCI artifact encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-registry" })
}

resource "aws_kms_alias" "registry" {
  name          = "alias/${var.name_prefix}-registry"
  target_key_id = aws_kms_key.registry.key_id
}

resource "aws_ecr_repository" "staging" {
  name                 = "${var.name_prefix}/runtime"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.registry.arn
  }

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name                 = "${var.name_prefix}-runtime"
    SignaturePolicy      = "keyless-signature-required"
    ProvenancePolicy     = "slsa-provenance-required"
    DeploymentReferences = "digest-only"
  })
}

resource "aws_ecr_lifecycle_policy" "staging" {
  repository = aws_ecr_repository.staging.name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Retain the bounded set of newest immutable staging images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.retained_image_count
        }
        action = { type = "expire" }
      },
    ]
  })
}

resource "aws_iam_policy" "publisher" {
  name        = "${var.name_prefix}-artifact-publish"
  description = "Publish images only to the exact private staging repository"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "RepositoryUpload"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:CompleteLayerUpload",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart",
        ]
        Resource = aws_ecr_repository.staging.arn
      },
      {
        Sid      = "AuthorizationToken"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
    ]
  })
  tags = var.tags
}

resource "aws_iam_policy" "puller" {
  name        = "${var.name_prefix}-artifact-pull"
  description = "Pull images only from the exact private staging repository"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "RepositoryPull"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
        ]
        Resource = aws_ecr_repository.staging.arn
      },
      {
        Sid      = "AuthorizationToken"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
    ]
  })
  tags = var.tags
}
