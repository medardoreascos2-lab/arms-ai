output "service_role_arns" {
  value = { for name, role in aws_iam_role.service : name => role.arn }
}

output "oidc_contract" {
  description = "Public validation metadata only; no client secret or tenant is created."
  value = {
    issuer                    = var.oidc_issuer
    audience                  = var.oidc_audience
    jwks_uri                  = var.oidc_jwks_uri
    allowed_algorithms        = ["RS256", "ES256"]
    required_claims           = sort(tolist(local.required_claims))
    tenant_claim              = var.tenant_claim
    role_claim                = var.role_claim
    role_mapping              = local.role_mapping
    key_rotation_max_age_days = var.key_rotation_max_age_days
    reject_unknown_key_ids    = true
    reject_missing_tenant     = true
    reject_missing_role       = true
    tenant_created            = false
  }
}
