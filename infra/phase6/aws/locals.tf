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

module "database" {
  source = "./modules/database"

  name_prefix               = local.name_prefix
  database_subnet_ids       = module.network.private_database_subnet_ids
  database_security_group_id = module.network.security_group_ids.database
  instance_class            = var.database_instance_class
  multi_az                  = var.database_multi_az
  backup_retention_days     = var.database_backup_retention_days
  max_connections           = var.database_max_connections
  tags                      = local.required_tags
}

module "secrets" {
  source = "./modules/secrets"

  name_prefix        = local.name_prefix
  environment        = var.environment
  rotation_lambda_arn = var.rotation_hook_arn
  tags               = local.required_tags
}

module "identity" {
  source = "./modules/identity"

  name_prefix              = local.name_prefix
  environment              = var.environment
  oidc_issuer              = var.oidc_issuer
  oidc_audience            = var.oidc_audience
  oidc_jwks_uri            = var.oidc_jwks_uri
  secret_reader_policy_arns = module.secrets.reader_policy_arns
  tags                     = local.required_tags
}

module "observability" {
  source = "./modules/observability"

  name_prefix       = local.name_prefix
  log_retention_days = var.telemetry_log_retention_days
  tags              = local.required_tags
}

module "backup" {
  source = "./modules/backup"

  name_prefix   = local.name_prefix
  bucket_name   = var.backup_bucket_name
  retention_days = var.backup_retention_days
  tags          = local.required_tags
}
