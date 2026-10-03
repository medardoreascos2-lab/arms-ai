variable "name_prefix" {
  type = string
}

variable "vpc_cidr" {
  type = string

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr must be a valid IPv4 CIDR."
  }
}

variable "availability_zone_count" {
  type    = number
  default = 2

  validation {
    condition     = var.availability_zone_count == 2
    error_message = "Phase 6 staging requires exactly two availability zones."
  }
}

variable "allowed_ingress_cidrs" {
  description = "Operator-approved HTTPS source ranges; empty keeps ingress closed."
  type        = set(string)
  default     = []

  validation {
    condition = alltrue([
      for cidr in var.allowed_ingress_cidrs :
      can(cidrnetmask(cidr)) && cidr != "0.0.0.0/0"
    ])
    error_message = "Ingress CIDRs must be valid and cannot allow the entire internet."
  }
}

variable "api_container_port" {
  type    = number
  default = 8000

  validation {
    condition     = var.api_container_port >= 1024 && var.api_container_port <= 65535
    error_message = "api_container_port must be an unprivileged TCP port."
  }
}

variable "staging_hostname" {
  description = "Approved DNS name placeholder; null creates no DNS records."
  type        = string
  default     = null
  nullable    = true
}

variable "certificate_arn" {
  description = "Approved ACM certificate ARN placeholder; null creates no listener."
  type        = string
  default     = null
  nullable    = true
}

variable "tags" {
  type = map(string)
}
