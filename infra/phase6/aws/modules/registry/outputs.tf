output "repository_arn" {
  value = aws_ecr_repository.staging.arn
}

output "repository_url" {
  value = aws_ecr_repository.staging.repository_url
}

output "publisher_policy_arn" {
  value = aws_iam_policy.publisher.arn
}

output "puller_policy_arn" {
  value = aws_iam_policy.puller.arn
}

output "release_contract" {
  value = {
    private                    = true
    immutable_tags             = true
    digest_only_deployment     = true
    scan_on_push               = true
    maximum_critical_findings  = 0
    maximum_high_findings      = 0
    signature_required         = true
    provenance_required        = true
    retained_image_count       = var.retained_image_count
    external_upload_authorized = false
  }
}
