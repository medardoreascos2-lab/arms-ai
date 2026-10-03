variable "name_prefix" {
  type = string
}

variable "log_retention_days" {
  type    = number
  default = 30

  validation {
    condition     = contains([14, 30, 60, 90], var.log_retention_days)
    error_message = "log retention must use the reviewed staging allowlist."
  }
}

variable "alarm_evaluation_periods" {
  type    = number
  default = 3

  validation {
    condition     = var.alarm_evaluation_periods >= 2 && var.alarm_evaluation_periods <= 5
    error_message = "alarm evaluation periods must be between 2 and 5."
  }
}

variable "tags" {
  type = map(string)
}
