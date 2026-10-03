variable "name_prefix" {
  type = string
}

variable "bucket_name" {
  description = "Globally unique operator-approved staging backup bucket name."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{8,61}[a-z0-9]$", var.bucket_name))
    error_message = "bucket_name must be a valid explicit S3 bucket name."
  }
}

variable "retention_days" {
  type    = number
  default = 30

  validation {
    condition     = var.retention_days >= 7 && var.retention_days <= 365
    error_message = "backup retention must remain between 7 and 365 days."
  }
}

variable "object_lock_enabled" {
  description = "Enable governance-mode object retention at bucket creation."
  type        = bool
  default     = true
}

variable "tags" {
  type = map(string)
}
