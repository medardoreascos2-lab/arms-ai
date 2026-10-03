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

module "network" {
  source = "./modules/network"

  name_prefix          = local.name_prefix
  vpc_cidr             = var.vpc_cidr
  allowed_ingress_cidrs = var.allowed_ingress_cidrs
  staging_hostname     = var.staging_hostname
  certificate_arn      = var.certificate_arn
  tags                 = local.required_tags
}
