locals {
  name_prefix = "${var.project_name}-${var.environment}"

  required_tags = merge(var.additional_tags, {
    Application = "ARMS-AI"
    Environment = "staging"
    ManagedBy   = "terraform"
    Authority   = "no-broker-no-live-no-production"
    Owner       = var.owner
    CostCenter  = var.cost_center
  })
}
