variable "aws_region" {
  description = "Operator-approved AWS region for isolated external staging."
  type        = string

  validation {
    condition     = can(regex("^[a-z]{2}(-[a-z]+)+-[0-9]+$", var.aws_region))
    error_message = "aws_region must be an explicit AWS region identifier."
  }
}

variable "project_name" {
  description = "Stable resource-name prefix."
  type        = string
  default     = "arms-ai"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,24}$", var.project_name))
    error_message = "project_name must contain 3-24 lowercase letters, digits, or hyphens."
  }
}

variable "environment" {
  description = "Fixed non-production environment boundary."
  type        = string
  default     = "staging"

  validation {
    condition     = var.environment == "staging"
    error_message = "Phase 6 infrastructure is staging-only."
  }
}

variable "owner" {
  description = "Non-secret owner/team tag used for cost and audit attribution."
  type        = string

  validation {
    condition     = length(trimspace(var.owner)) >= 3
    error_message = "owner must be an explicit non-secret team identifier."
  }
}

variable "cost_center" {
  description = "Non-secret cost attribution tag approved before provisioning."
  type        = string

  validation {
    condition     = length(trimspace(var.cost_center)) >= 2
    error_message = "cost_center must be explicit."
  }
}

variable "additional_tags" {
  description = "Additional non-secret tags; protected tags cannot be overridden."
  type        = map(string)
  default     = {}

  validation {
    condition = length(setintersection(
      toset(keys(var.additional_tags)),
      toset(["Application", "Environment", "ManagedBy", "Authority", "Owner", "CostCenter"])
    )) == 0
    error_message = "additional_tags cannot override protected governance tags."
  }
}
