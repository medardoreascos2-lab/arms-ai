variable "name_prefix" {
  type = string
}

variable "environment" {
  type = string

  validation {
    condition     = var.environment == "staging"
    error_message = "Phase 6 identities are staging-only."
  }
}

variable "oidc_issuer" {
  description = "Operator-approved external issuer; no tenant is created by this module."
  type        = string

  validation {
    condition     = can(regex("^https://[^/]+(/.*)?$", var.oidc_issuer))
    error_message = "oidc_issuer must use HTTPS."
  }
}

variable "oidc_audience" {
  type = string

  validation {
    condition     = length(trimspace(var.oidc_audience)) >= 8
    error_message = "oidc_audience must be an explicit staging audience."
  }
}

variable "oidc_jwks_uri" {
  type = string

  validation {
    condition     = can(regex("^https://[^/]+/.+$", var.oidc_jwks_uri))
    error_message = "oidc_jwks_uri must be an explicit HTTPS URI."
  }
}

variable "tenant_claim" {
  type    = string
  default = "tenant_id"
}

variable "role_claim" {
  type    = string
  default = "roles"
}

variable "key_rotation_max_age_days" {
  type    = number
  default = 90

  validation {
    condition     = var.key_rotation_max_age_days >= 7 && var.key_rotation_max_age_days <= 90
    error_message = "OIDC key rotation age must be between 7 and 90 days."
  }
}

variable "secret_reader_policy_arns" {
  description = "Exact per-service Secrets Manager reader policies."
  type        = map(string)

  validation {
    condition = setequals(
      toset(keys(var.secret_reader_policy_arns)),
      toset(["api", "worker", "scheduler", "research"])
    )
    error_message = "Secret reader policies must cover exactly api, worker, scheduler, and research."
  }
}

variable "tags" {
  type = map(string)
}
