variable "name_prefix" {
  type = string
}

variable "database_subnet_ids" {
  type = list(string)

  validation {
    condition     = length(var.database_subnet_ids) == 2
    error_message = "The staging database requires two private subnets."
  }
}

variable "database_security_group_id" {
  type = string
}

variable "engine_major_version" {
  type    = string
  default = "16"

  validation {
    condition     = contains(["16", "17"], var.engine_major_version)
    error_message = "Use an explicitly supported PostgreSQL major version."
  }
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"

  validation {
    condition     = contains(["db.t4g.micro", "db.t4g.small", "db.m7g.large"], var.instance_class)
    error_message = "instance_class must use the reviewed staging allowlist."
  }
}

variable "allocated_storage_gib" {
  type    = number
  default = 20

  validation {
    condition     = var.allocated_storage_gib >= 20 && var.allocated_storage_gib <= 200
    error_message = "allocated_storage_gib must remain within the reviewed staging bounds."
  }
}

variable "max_allocated_storage_gib" {
  type    = number
  default = 100

  validation {
    condition     = var.max_allocated_storage_gib >= 20 && var.max_allocated_storage_gib <= 500
    error_message = "max_allocated_storage_gib must remain within the reviewed staging bounds."
  }
}

variable "backup_retention_days" {
  type    = number
  default = 7

  validation {
    condition     = var.backup_retention_days >= 7 && var.backup_retention_days <= 35
    error_message = "backup retention must be between 7 and 35 days."
  }
}

variable "multi_az" {
  description = "Explicit staging cost/availability decision."
  type        = bool
  default     = false
}

variable "max_connections" {
  type    = number
  default = 100

  validation {
    condition     = var.max_connections >= 20 && var.max_connections <= 500
    error_message = "max_connections must remain within the reviewed pool bound."
  }
}

variable "maintenance_window" {
  type    = string
  default = "sun:07:00-sun:08:00"
}

variable "backup_window" {
  type    = string
  default = "05:00-06:00"
}

variable "tags" {
  type = map(string)
}
