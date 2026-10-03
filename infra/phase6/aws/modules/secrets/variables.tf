variable "name_prefix" {
  type = string
}

variable "environment" {
  type = string

  validation {
    condition     = var.environment == "staging"
    error_message = "Phase 6 secrets are staging-only."
  }
}

variable "rotation_lambda_arn" {
  description = "Optional approved rotation hook; null creates no rotation binding."
  type        = string
  default     = null
  nullable    = true
}

variable "rotation_days" {
  type    = number
  default = 30

  validation {
    condition     = var.rotation_days >= 7 && var.rotation_days <= 90
    error_message = "rotation_days must remain between 7 and 90."
  }
}

variable "tags" {
  type = map(string)
}
