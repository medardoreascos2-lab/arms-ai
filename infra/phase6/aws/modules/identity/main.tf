locals {
  service_identities = toset([
    "api",
    "worker",
    "scheduler",
    "research",
    "migration",
    "maintenance",
    "backup",
    "restore",
    "telemetry",
    "artifact-publisher",
  ])

  role_mapping = {
    viewer     = ["staging:read"]
    operator   = ["staging:read", "staging:operate"]
    researcher = ["staging:read", "research:submit", "research:read"]
  }

  required_claims = toset([
    "sub",
    "iss",
    "aud",
    "iat",
    "exp",
    var.tenant_claim,
    var.role_claim,
  ])

  workload_policy_attachments = merge([
    for service, policy_arns in var.workload_policy_arns : {
      for index, policy_arn in policy_arns :
      "${service}:${index}" => {
        service    = service
        policy_arn = policy_arn
      }
    }
  ]...)
}

data "aws_iam_policy_document" "ecs_tasks" {
  statement {
    sid     = "EcsTaskAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "service" {
  for_each = local.service_identities

  name                 = "${var.name_prefix}-${each.key}"
  description          = "Isolated ${var.environment} ${each.key} workload identity"
  assume_role_policy   = data.aws_iam_policy_document.ecs_tasks.json
  max_session_duration = 3600

  tags = merge(var.tags, {
    Name       = "${var.name_prefix}-${each.key}"
    Service    = each.key
    Privileges = "minimum-attached-only"
  })
}

resource "aws_iam_role_policy_attachment" "secret_reader" {
  for_each = var.secret_reader_policy_arns

  role       = aws_iam_role.service[each.key].name
  policy_arn = each.value
}

resource "aws_iam_role_policy_attachment" "workload" {
  for_each = local.workload_policy_attachments

  role       = aws_iam_role.service[each.value.service].name
  policy_arn = each.value.policy_arn
}
